"""base class for evaluation (LLM-Enhanced Version)"""
import collections
import html
import json
import time
import urllib
import os
from pathlib import Path
from typing import Any, Tuple, Union, List

from beartype import beartype
from nltk.tokenize import word_tokenize  # type: ignore
from playwright.sync_api import CDPSession, Page
from openai import OpenAI  # Added for DeepSeek

from webarena.browser_env.actions import Action
from webarena.browser_env.utils import StateInfo

# 保留原有的 helper 引用，防止其他地方依赖，但本脚本中主要逻辑已被 LLM 替代
from webarena.evaluation_harness.helper_functions import (
    PseudoPage,
    # 下面这些在 LLM 版中不再是核心，但为了兼容性保留导入
    gitlab_get_project_memeber_role, 
    llm_fuzzy_match,
    llm_ua_match,
    reddit_get_post_url,
    shopping_get_latest_order_url,
    shopping_get_sku_latest_review_author,
    shopping_get_sku_latest_review_rating,
)

# --- DeepSeek Configuration ---
DEEPSEEK_API_KEY = "sk-41fae6597fd14d6fa2c5c4068c0e5760"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

Trajectory = list[Union[Action, StateInfo]]

class LLMJudge:
    """Helper class to handle DeepSeek API calls for evaluation."""
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )

    def judge(self, system_prompt: str, user_prompt: str) -> float:
        """Returns 1.0 for success, 0.0 for failure."""
        try:
            response = self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0, # Deterministic evaluation
                max_tokens=10
            )
            content = response.choices[0].message.content.strip().lower()
            # Check for explicit yes/pass indicators
            if "yes" in content or "true" in content or "pass" in content or "correct" in content:
                return 1.0
            return 0.0
        except Exception as e:
            print(f"[LLM Judge Error]: {e}")
            # Fallback or strict fail on error? usually fail to be safe, or 0.5?
            # returning 0.0 to avoid false positives on API errors
            return 0.0

# Instantiate a global judge
llm_judge = LLMJudge()


class Evaluator(object):
    def __init__(self, eval_tag: str = "") -> None:
        self.eval_tag = eval_tag

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession,
    ) -> float:
        raise NotImplementedError

    @staticmethod
    def get_last_action(trajectory: Trajectory) -> Action:
        try:
            last_action = trajectory[-1]
        except Exception:
            raise ValueError(
                "The last element of trajectory should be an action."
            )
        return last_action  # type: ignore[return-value]


class StringEvaluator(Evaluator):
    """
    Check whether the answer is correct using DeepSeek LLM.
    Handles Exact Match, Must Include, and Fuzzy Match via a unified semantic check.
    """

    @staticmethod
    @beartype
    def clean_answer(answer: str) -> str:
        answer = answer.strip()
        if answer.startswith("'") and answer.endswith("'"):
            answer = answer[1:-1]
        elif answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1]
        return answer.lower()

    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage | None = None,
        client: CDPSession | None = None,
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        last_action = self.get_last_action(trajectory)
        pred = last_action.get("answer", "")
        intent = configs.get("intent", "No intent provided")
        
        # 收集所有的参考答案
        reference_answers = []
        eval_config = configs["eval"].get("reference_answers", {})
        
        # 将原有的各种 key (exact_match, must_include, fuzzy_match) 里的值都提取出来作为参考
        if isinstance(eval_config, dict):
            for key, val in eval_config.items():
                if isinstance(val, list):
                    reference_answers.extend(val)
                elif isinstance(val, str):
                    reference_answers.append(val)
        
        # 处理 N/A 情况
        if not reference_answers:
             # 有些配置可能直接在 string_note 里，或者没有明确 reference
             reference_answers.append(configs["eval"].get("string_note", "N/A"))

        # Construct Prompt for LLM
        system_prompt = (
            "You are an impartial judge evaluating the performance of a web agent. "
            "Your task is to determine if the agent's predicted answer semantically matches "
            "the reference answer(s) given the user's intent.\n"
            "Ignore case sensitivity and minor formatting differences.\n"
            "If the reference is 'N/A' and the agent provides a valid explanation for why the task failed, count it as correct.\n"
            "Return only 'YES' if it matches/satisfies the requirement, or 'NO' if it does not."
        )

        user_prompt = (
            f"User Intent: {intent}\n"
            f"Reference Answer(s): {reference_answers}\n"
            f"Agent Prediction: {pred}\n\n"
            f"Is the prediction correct?"
        )

        print(f"--- [StringEvaluator LLM Check] ---\nPred: {pred}\nRef: {reference_answers}")
        score = llm_judge.judge(system_prompt, user_prompt)
        print(f"Result: {score}")
        
        return score


class URLEvaluator(Evaluator):
    """Check URL matching using DeepSeek LLM"""

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession | None = None,
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        pred_url = page.url
        ref_url_str = configs["eval"]["reference_url"] # Usually a string like "url1 |OR| url2"
        intent = configs.get("intent", "")
        
        # Logic to handle '|OR|' for clarity in prompt, though LLM usually handles raw string well
        ref_urls = ref_url_str.split(" |OR| ")

        system_prompt = (
            "You are a web navigation evaluator. Check if the current URL matches the target URL criteria.\n"
            "1. Ignore dynamic parameters like session IDs, tracking codes (utm_source), or random hashes unless they are clearly part of the resource identifier.\n"
            "2. Focus on the domain, path, and critical query parameters (like product ID or search query).\n"
            "3. If the user intent implies reaching a specific page, and the current URL reflects that page, return YES.\n"
            "Return only 'YES' for a match, 'NO' for a mismatch."
        )

        user_prompt = (
            f"User Intent: {intent}\n"
            f"Allowed Reference URL(s): {ref_urls}\n"
            f"Current Actual URL: {pred_url}\n\n"
            f"Is the agent at the correct location?"
        )

        print(f"--- [URLEvaluator LLM Check] ---\nActual: {pred_url}\nRef: {ref_urls}")
        score = llm_judge.judge(system_prompt, user_prompt)
        print(f"Result: {score}")

        return score


class HTMLContentEvaluator(Evaluator):
    """
    Check whether the contents appear in the page.
    (Keeping original logic mostly, as this often requires DOM extraction which LLM can't see directly 
    unless we feed the whole HTML, which might exceed context windows or be slow. 
    However, we use the cleaned StringEvaluator methods if needed for checking content match).
    """

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession | None = None,
    ) -> float:
        with open(config_file, "r") as f:
            configs = json.load(f)

        targets = configs["eval"]["program_html"]

        score = 1.0
        for target in targets:
            target_url: str = target["url"]
            if target_url.startswith("func"):
                func = target_url.split("func:")[1]
                func = func.replace("__last_url__", page.url)
                target_url = eval(func)

            locator: str = target["locator"]

            # navigate
            prev_page = None
            if target_url != "last":
                try:
                    prev_page = page
                    page = page.context.new_page()
                    page.goto(target_url)
                    time.sleep(3)
                except Exception:
                    # Navigation failed
                    return 0.0

            # Select Element
            selected_element = ""
            if not locator.strip():
                selected_element = page.content()
            elif locator.startswith("document.") or locator.startswith("[...document."):
                if "prep_actions" in target:
                    try:
                        for prep_action in target["prep_actions"]:
                            page.evaluate(f"() => {prep_action}")
                    except Exception:
                        pass
                try:
                    selected_element = str(page.evaluate(f"() => {locator}"))
                except Exception:
                    selected_element = ""
            elif locator.startswith("func:"):
                func = locator.split("func:")[1]
                func = func.replace("__page__", "page")
                try:
                    selected_element = eval(func)
                except:
                    selected_element = ""
            else:
                # Playwright standard locator could be added here if needed
                pass

            selected_element = html.unescape(str(selected_element))
            
            # --- Use LLM for Content Matching within HTML Evaluator too ---
            # To ensure consistency, we use the same LLM logic for checking if the content exists
            
            required_contents = []
            if "exact_match" in target["required_contents"]:
                required_contents.append(target["required_contents"]["exact_match"])
            if "must_include" in target["required_contents"]:
                # must_include in WebArena is usually a list where ALL must be present.
                # However, inside the list, strings might be split by |OR|.
                # We flatten this for the LLM prompt.
                val = target["required_contents"]["must_include"]
                if isinstance(val, list):
                    required_contents.extend(val)
                else:
                    required_contents.append(val)

            if not required_contents:
                # No requirements? pass.
                continue

            # Prompt for HTML content check
            system_prompt = (
                "You are checking if specific information exists within a text extracted from a webpage.\n"
                "The user needs to verify if the 'Required Information' is present in the 'Extracted Text'.\n"
                "Return YES if the information is present, NO otherwise."
            )
            user_prompt = (
                f"Required Information: {required_contents}\n"
                f"Extracted Text (from website): {selected_element[:4000]} ... [truncated]\n\n" 
                f"Is the required information present?"
            )

            print(f"!!!!!!!!!!!!!selected: {selected_element}")
            
            # Note: truncated selected_element to avoid token limit if it's full innerHTML
            # If selected_element is huge, this might need better handling (RAG or chunking), 
            # but usually 'locator' extracts specific small text.
            
            cur_score = llm_judge.judge(system_prompt, user_prompt)
            score *= cur_score

            if prev_page:
                page.close()
                page = prev_page
                prev_page = None

        print(f"Result: {score}")
        return score


class EvaluatorComb:
    def __init__(self, evaluators: list[Evaluator]) -> None:
        self.evaluators = evaluators

    @beartype
    def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | PseudoPage,
        client: CDPSession | None,
    ) -> float:
        score = 1.0
        for evaluator in self.evaluators:
            cur_score = evaluator(trajectory, config_file, page, client)
            score *= cur_score
            if score == 0.0: # Early exit optimization
                break
        return score


@beartype
def evaluator_router(config_file: Path | str) -> EvaluatorComb:
    """Router to get the evaluator class"""
    with open(config_file, "r") as f:
        configs = json.load(f)

    eval_types = configs["eval"]["eval_types"]
    evaluators: list[Evaluator] = []
    for eval_type in eval_types:
        match eval_type:
            case "string_match":
                evaluators.append(StringEvaluator())
            case "url_match":
                evaluators.append(URLEvaluator())
            case "program_html":
                evaluators.append(HTMLContentEvaluator())
            case _:
                raise ValueError(f"eval_type {eval_type} is not supported")

    return EvaluatorComb(evaluators)