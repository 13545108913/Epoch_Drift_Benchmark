"""base class for evaluation (LLM-Enhanced Async Version)"""

import asyncio
import collections
import html
import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, List, Union

from openai import AsyncOpenAI  # 新增依赖
from playwright.async_api import CDPSession, Page
from typing_extensions import TypedDict

# 保持原有的 SkillWeaver 引用
from skillweaver.environment import State
from skillweaver.evaluation.webarena_config import _resolve_start_url
from skillweaver.util.perfmon import monitor
from skillweaver.evaluation.webarena_helper_functions import (
    PseudoPage, 
    # 下面这些辅助函数在 LLM 版中可能用不到，但为了兼容性保留
    gitlab_get_project_member_role, 
    llm_fuzzy_match, 
    llm_ua_match,
    reddit_get_post_url, 
    shopping_get_latest_order_url,
    shopping_get_sku_latest_review_author,
    shopping_get_sku_latest_review_rating
)

# --- DeepSeek Configuration ---
DEEPSEEK_API_KEY = "sk-41fae6597fd14d6fa2c5c4068c0e5760"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

Trajectory = tuple[list[State], list[dict]]


class CheckResult(TypedDict):
    success: bool
    reason: str


class Outcome(TypedDict):
    score: float
    checks: list[CheckResult]


class LLMJudge:
    """Helper class to handle DeepSeek API calls asynchronously."""
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )

    async def check(self, system_prompt: str, user_prompt: str) -> CheckResult:
        """
        Sends request to LLM and parses the result into a CheckResult.
        We ask the LLM to return JSON to make parsing robust.
        """
        try:
            response = await self.client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"} # DeepSeek supports JSON mode
            )
            content = response.choices[0].message.content
            result_json = json.loads(content)

            cmpl_tokens = response.usage.completion_tokens  # type: ignore
            prompt_tokens = response.usage.prompt_tokens  # type: ignore

            monitor.log_token_usage("general", "openai:" + DEEPSEEK_MODEL, prompt_tokens, cmpl_tokens)
            
            # Normalize keys just in case
            success = result_json.get("success", result_json.get("correct", False))
            reason = result_json.get("reason", "No reason provided by LLM.")
            
            return {"success": bool(success), "reason": reason}
            
        except Exception as e:
            # Fallback for API errors
            return {
                "success": False, 
                "reason": f"LLM Evaluation Failed: {str(e)}"
            }

# Global instance
llm_judge = LLMJudge()


class Evaluator(object):
    def __init__(self, eval_tag: str = "") -> None:
        self.eval_tag = eval_tag

    async def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page,
        client: CDPSession,
    ) -> Outcome:
        raise NotImplementedError


class StringEvaluator(Evaluator):
    """
    Check whether the answer is correct using DeepSeek LLM.
    Replaces rigid exact_match/must_include with semantic verification.
    """

    @staticmethod
    def clean_answer(answer: str) -> str:
        answer = answer.strip()
        if answer.startswith("'") and answer.endswith("'"):
            answer = answer[1:-1]
        elif answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1]
        return answer.lower()

    async def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page | None = None,
        client: CDPSession | None = None,
    ) -> Outcome:
        with open(config_file, "r") as f:
            configs = json.load(f)

        _, actions = trajectory

        # Extract Prediction
        if actions[-1].get("terminate_with_result"):
            pred = self.clean_answer(actions[-1]["terminate_with_result"])
        elif actions[-1].get("name") == "terminate":
            pred = self.clean_answer(actions[-1]["args"]["result"])
        else:
            return {
                "score": 0,
                "checks": [{
                    "reason": "Last action was non-terminal (likely truncated)",
                    "success": False,
                }],
            }

        # Gather References
        intent = configs.get("intent", "No intent provided")
        reference_answers = []
        eval_config = configs["eval"].get("reference_answers", {})
        
        # Flatten all reference types (exact, fuzzy, must_include) into a single list of criteria
        if isinstance(eval_config, dict):
            for key, val in eval_config.items():
                if isinstance(val, list):
                    reference_answers.extend(val)
                elif isinstance(val, str):
                    reference_answers.append(val)
        
        # Handle N/A logic
        string_note = configs["eval"].get("string_note", "")
        if string_note and string_note != "N/A":
             reference_answers.append(f"Or satisfy logic: {string_note}")

        # Construct Prompt
        system_prompt = (
            "You are a strict judge evaluating a Web Agent's performance. "
            "Compare the Agent's Prediction against the Reference Answers and the User Intent.\n"
            "Return a JSON object with two keys:\n"
            "- 'success': boolean (true if the prediction is semantically correct or strictly satisfies the conditions)\n"
            "- 'reason': string (a brief explanation)\n\n"
            "Rules:\n"
            "1. Ignore case and minor formatting issues.\n"
            "2. If the answer is 'N/A' and the agent explains effectively why it failed (and it matches the scenario), mark as true."
        )

        user_prompt = (
            f"User Intent: {intent}\n"
            f"Reference Answer(s): {reference_answers}\n"
            f"Agent Prediction: {pred}\n"
        )

        # Call LLM
        check_result = await llm_judge.check(system_prompt, user_prompt)
        
        return {
            "score": 1.0 if check_result["success"] else 0.0,
            "checks": [check_result]
        }


def clean_url(url: str) -> str:
    url = str(url)
    url = url.rstrip("/")
    return url


class URLEvaluator(Evaluator):
    """Check URL matching using LLM semantic understanding"""

    async def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page,
        client: CDPSession | None = None,
    ) -> Outcome:
        with open(config_file, "r") as f:
            configs = json.load(f)

        states, _ = trajectory
        
        # Current State
        actual_url = clean_url(states[-1].url)
        
        # Reference Config
        ref_url_raw = configs["eval"]["reference_url"]
        intent = configs.get("intent", "Navigate to the correct page.")
        
        # Pre-process references (resolve base URLs if needed)
        # We keep the logic of splitting |OR| to show the LLM valid options
        possible_urls = ref_url_raw.split(" |OR| ")
        resolved_refs = []
        for u in possible_urls:
            try:
                # Attempt to resolve if it's a relative path logic, otherwise keep string
                resolved = _resolve_start_url(u) 
                resolved_refs.append(clean_url(resolved))
            except:
                resolved_refs.append(u)

        system_prompt = (
            "You are evaluating if a Web Agent reached the correct URL. "
            "Return a JSON object with {'success': bool, 'reason': str}.\n"
            "Rules:\n"
            "1. Ignore session IDs, tracking params (utm_*, etc.), and random hashes.\n"
            "2. Focus on domain, path, and key query parameters (like product ID).\n"
            "3. If the User Intent implies being on a specific page type, and the Actual URL matches that type, mark true."
        )

        user_prompt = (
            f"User Intent: {intent}\n"
            f"Allowed Reference URL(s): {resolved_refs}\n"
            f"Actual URL: {actual_url}\n"
        )

        check_result = await llm_judge.check(system_prompt, user_prompt)

        return {
            "score": 1.0 if check_result["success"] else 0.0,
            "checks": [check_result]
        }


class HTMLContentEvaluator(Evaluator):
    """
    Check whether the contents appear in the page using LLM.
    Keeps Playwright for extraction, uses LLM for verification.
    """

    async def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page,
        client: CDPSession | None = None,
    ) -> Outcome:
        with open(config_file, "r") as f:
            configs = json.load(f)

        targets = configs["eval"]["program_html"]
        
        overall_score = 1.0
        checks: list[CheckResult] = []

        for target in targets:
            # --- 1. Navigation & Extraction Logic (Keep Strict Python/JS) ---
            target_url: str = target["url"]
            if target_url.startswith("func"):
                func = target_url.split("func:")[1]
                func = func.replace("__last_url__", page.url)
                try:
                    target_url = eval(func)
                except Exception as e:
                     checks.append({"success": False, "reason": f"Failed to eval target url func: {e}"})
                     return {"score": 0.0, "checks": checks}

            locator: str = target["locator"]

            # navigate
            if target_url != "last":
                try:
                    target_url = _resolve_start_url(target_url)
                    await page.goto(target_url)
                    await page.wait_for_load_state("load")
                    await asyncio.sleep(3) 
                except Exception as e:
                    checks.append({"success": False, "reason": f"Navigation failed: {e}"})
                    overall_score = 0.0
                    continue

            # Extract content
            selected_element = ""
            try:
                if not locator.strip():
                    selected_element = await page.content()
                elif locator.startswith("document.") or locator.startswith("[...document."):
                    if "prep_actions" in target:
                        for prep_action in target["prep_actions"]:
                            await page.evaluate(f"() => {prep_action}")
                    val = await page.evaluate(f"() => {locator}")
                    selected_element = str(val) if val else ""
                elif locator.startswith("func:"):
                    func = locator.split("func:")[1]
                    func = func.replace("__page__", "page")
                    # Note: eval here is risky but part of original logic. 
                    # Ideally this func needs 'page' in local scope or wrapped properly.
                    # Assuming the environment allows this eval execution context.
                    selected_element = eval(func) 
                else:
                    # Fallback standard locator
                    if await page.locator(locator).count() > 0:
                        selected_element = await page.locator(locator).first.inner_text()
            except Exception as e:
                checks.append({"success": False, "reason": f"Content extraction failed: {e}"})
                overall_score = 0.0
                continue

            selected_element = html.unescape(str(selected_element))
            
            # --- 2. LLM Evaluation Logic ---
            
            # Gather requirements
            required_contents = []
            if "exact_match" in target["required_contents"]:
                required_contents.append(f"Exact match: {target['required_contents']['exact_match']}")
            if "must_include" in target["required_contents"]:
                val = target["required_contents"]["must_include"]
                if isinstance(val, list):
                    required_contents.extend([f"Must include: {v}" for v in val])
                else:
                    required_contents.append(f"Must include: {val}")

            if not required_contents:
                continue

            # Truncate if content is too massive (e.g. full HTML) to save tokens/avoid errors
            # 15k chars is usually safe for modern contexts, adjust as needed.
            truncated_content = selected_element[:15000] + ("..." if len(selected_element) > 15000 else "")

            system_prompt = (
                "You are verifying if specific information is present in extracted web text. "
                "Return a JSON object with {'success': bool, 'reason': str}."
            )
            
            user_prompt = (
                f"Requirements: {required_contents}\n"
                f"Extracted Text: {truncated_content}\n\n"
                f"Is the required information present in the text?"
            )

            check_result = await llm_judge.check(system_prompt, user_prompt)
            
            checks.append(check_result)
            if not check_result["success"]:
                overall_score = 0.0
            
            # Restore state if needed (optional optimization, original script didn't explicitly go back)

        return {"score": overall_score, "checks": checks}


class EvaluatorComb:
    def __init__(self, evaluators: list[Evaluator]) -> None:
        self.evaluators = evaluators

    async def __call__(
        self,
        trajectory: Trajectory,
        config_file: Path | str,
        page: Page,
        client: CDPSession,
    ) -> Outcome:
        score = 1.0
        checks = []
        for evaluator in self.evaluators:
            result = await evaluator(trajectory, config_file, page, client)
            score *= result["score"]
            checks += result["checks"]
            
            # Optional: Fail fast
            if score == 0.0:
                break
                
        return {"score": score, "checks": checks}


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