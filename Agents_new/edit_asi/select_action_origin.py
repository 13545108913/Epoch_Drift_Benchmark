import time
import traceback
import json
import os
from types import SimpleNamespace
from typing import Any

from pathlib import Path
from datetime import datetime
import re

import playwright.sync_api
from browsergym.core.env import BrowserEnv, logger

from rewrite import rewrite_bid_action_to_selector

MY_MODEL = os.getenv("my_model")
agent_args = None


def execute_python_code(
    code: str,
    page: playwright.sync_api.Page,
    send_message_to_user: callable,
    report_infeasible_instructions: callable,
    **additional_globals,
):
    """
    Executes Python code in a new context.
    """
    globals_dict = {
        "page": page,
        "send_message_to_user": send_message_to_user,
        "report_infeasible_instructions": report_infeasible_instructions,
        **additional_globals,
    }
    exec(code, globals_dict)


class SandboxEnvProxy:
    """
    Minimal safe proxy passed into candidate sandbox execution.

    Goal:
    - expose only harmless fields some action code may expect
    - avoid mutating the real env during sandbox trial
    """

    def __init__(self, base_env: BrowserEnv, sandbox_page: playwright.sync_api.Page):
        self.page = sandbox_page
        self.context = sandbox_page.context
        self.chat = SimpleNamespace(add_message=lambda role, msg: None)
        self.infeasible_message_received = False
        self.last_action_error = ""
        self.last_action = ""
        self.action_mapping = base_env.action_mapping

        # Optional readonly references if action code inspects them
        self.task_kwargs = getattr(base_env, "task_kwargs", None)
        self.viewport = getattr(base_env, "viewport", None)

    def __getattr__(self, name):
        """
        Block accidental fallback to the real env.
        """
        raise AttributeError(f"SandboxEnvProxy has no attribute '{name}'")


def capture_form_state(page: playwright.sync_api.Page):
    return page.evaluate(
        """
() => {
    const elements = Array.from(document.querySelectorAll("input, textarea, select"));
    return elements.map((el, idx) => {
        const tag = el.tagName.toLowerCase();
        const type = (el.type || "").toLowerCase();
        return {
            idx,
            tag,
            type,
            name: el.name || "",
            id: el.id || "",
            placeholder: el.getAttribute("placeholder") || "",
            ariaLabel: el.getAttribute("aria-label") || "",
            value: el.value,
            checked: !!el.checked,
            selectedIndex: el.selectedIndex ?? null
        };
    });
}
"""
    )


def restore_form_state(page: playwright.sync_api.Page, form_state):
    page.evaluate(
        """
(formState) => {
    const all = Array.from(document.querySelectorAll("input, textarea, select"));

    function pick(item) {
        let candidates = all;

        if (item.id) {
            const el = document.getElementById(item.id);
            if (el && ["input", "textarea", "select"].includes(el.tagName.toLowerCase())) {
                return el;
            }
        }

        if (item.name) {
            const byName = all.filter(el => (el.name || "") === item.name);
            if (byName.length === 1) return byName[0];
        }

        if (item.placeholder) {
            const byPh = all.filter(el => (el.getAttribute("placeholder") || "") === item.placeholder);
            if (byPh.length === 1) return byPh[0];
        }

        if (item.ariaLabel) {
            const byAria = all.filter(el => (el.getAttribute("aria-label") || "") === item.ariaLabel);
            if (byAria.length === 1) return byAria[0];
        }

        return all[item.idx] || null;
    }

    for (const item of formState) {
        const el = pick(item);
        if (!el) continue;

        const tag = el.tagName.toLowerCase();
        const type = (el.type || "").toLowerCase();

        if (tag === "input") {
            if (type === "checkbox" || type === "radio") {
                el.checked = !!item.checked;
            } else {
                el.value = item.value ?? "";
            }
        } else if (tag === "textarea") {
            el.value = item.value ?? "";
        } else if (tag === "select") {
            if (item.selectedIndex !== null && item.selectedIndex >= 0) {
                el.selectedIndex = item.selectedIndex;
            }
        }

        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }
}
""",
        form_state,
    )


def create_sandbox_page(env):
    base_env = env.unwrapped
    real_page = base_env.page
    real_context = base_env.context

    storage_state = real_context.storage_state()
    browser = real_context.browser
    form_state = capture_form_state(real_page)

    viewport_size = None
    try:
        viewport_size = real_page.viewport_size
    except Exception:
        viewport_size = None

    sandbox_context = browser.new_context(
        storage_state=storage_state,
        viewport=viewport_size,
    )
    sandbox_page = sandbox_context.new_page()
    sandbox_page.goto(real_page.url, wait_until="domcontentloaded")

    try:
        restore_form_state(sandbox_page, form_state)
    except Exception as e:
        logger.warning(f"restore_form_state failed: {e}")

    return sandbox_context, sandbox_page


def _safe_aria_snapshot(page: playwright.sync_api.Page, max_len: int = 6000) -> str:
    """
    Prefer Playwright locator('body').aria_snapshot() when available.
    Falls back to a compact error marker.
    """
    try:
        body = page.locator("body")
        if hasattr(body, "aria_snapshot"):
            txt = body.aria_snapshot(timeout=1500)
            if txt:
                return txt[:max_len]
    except Exception as e:
        return f"[ARIA_SNAPSHOT_ERROR] {type(e).__name__}: {e}"[:max_len]

    return "[ARIA_SNAPSHOT_UNAVAILABLE]"


def extract_page_state(
    page: playwright.sync_api.Page,
    fallback_obs: dict | None = None,
    axtree_max_len: int = 6000,
    text_max_len: int = 2000,
):
    """
    Compact evaluator state:
    - url
    - title
    - visible_text
    - axtree_txt (prefer aria snapshot YAML)
    """
    title = ""
    try:
        title = page.title()
    except Exception:
        pass

    url = ""
    try:
        url = page.url
    except Exception:
        pass

    visible_text = ""
    try:
        visible_text = page.evaluate(
            """
(maxLen) => {
    const text = document.body ? document.body.innerText : "";
    return text.slice(0, maxLen);
}
""",
            text_max_len,
        )
    except Exception:
        pass

    axtree_txt = _safe_aria_snapshot(page, max_len=axtree_max_len)

    if (
        (not axtree_txt or axtree_txt.startswith("[ARIA_SNAPSHOT_"))
        and fallback_obs is not None
    ):
        obs_ax = (fallback_obs.get("axtree_txt", "") or "").strip()
        if obs_ax:
            axtree_txt = obs_ax[:axtree_max_len]

    return {
        "url": url,
        "title": title,
        "visible_text": visible_text,
        "axtree_txt": axtree_txt,
    }


def is_safe_for_sandbox(action: str) -> bool:
    """
    Block obviously risky actions from sandbox trial.
    This is heuristic and conservative.
    """
    lower = action.lower()

    risky_keywords = [
        "send_message_to_user",
        "send_msg_to_user",
    ]
    return not any(k in lower for k in risky_keywords)

def _safe_filename(s: str, max_len: int = 80) -> str:
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r'[\\/:*?"<>|`]', "_", s)
    s = s.replace("(", "_").replace(")", "_").replace(",", "_")
    s = re.sub(r"_+", "_", s).strip("._")
    if not s:
        s = "action"
    return s[:max_len]


def save_sandbox_screenshot(page: playwright.sync_api.Page, action: str, ok: bool, folder: str = "photo") -> str | None:
    try:
        out_dir = Path(folder)
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        action_name = _safe_filename(action)
        status = "ok" if ok else "error"
        path = out_dir / f"{ts}_{status}_{action_name}.png"

        page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception as e:
        logger.warning(f"save_sandbox_screenshot failed: {e}")
        return None
    
def page_changed_meaningfully(before, after) -> bool:
    if before["url"] != after["url"]:
        return True
    if before["title"] != after["title"]:
        return True
    if before["visible_text"][:500] != after["visible_text"][:500]:
        return True
    if before["axtree_txt"][:1000] != after["axtree_txt"][:1000]:
        return True
    return False

def try_action_on_sandbox(env, action: str, current_obs: dict | None = None):
    base_env = env.unwrapped
    sandbox_context = None

    try:
        sandbox_context, sandbox_page = create_sandbox_page(env)
        before_state = extract_page_state(sandbox_page, fallback_obs=current_obs)

        captured_messages = []
        infeasible_messages = []

        def send_message_to_user(text: str):
            if not isinstance(text, str):
                raise ValueError(f"Forbidden value: {text} is not a string")
            captured_messages.append(text)

        def report_infeasible_instructions(reason: str):
            if not isinstance(reason, str):
                raise ValueError(f"Forbidden value: {reason} is not a string")
            infeasible_messages.append(reason)

        # if base_env.action_mapping:
        #     code = base_env.action_mapping(action)
        # else:
        #     code = action

        rewritten = None
        try:
            rewritten = rewrite_bid_action_to_selector(action, env=env)
        except Exception as e:
            logger.warning(f"rewrite failed for action {action}: {e}")

        if rewritten is not None:
            code = rewritten
            rewrite_info = {
                "rewritten": True,
                "rewritten_code": rewritten,
            }
        else:
            if base_env.action_mapping:
                code = base_env.action_mapping(action)
            else:
                code = action
            rewrite_info = {
                "rewritten": False,
                "rewritten_code": None,
            }
        
        print(f"Action: {action}, {rewrite_info}")

        sandbox_env = SandboxEnvProxy(base_env, sandbox_page)

        execute_python_code(
            code,
            sandbox_page,
            send_message_to_user=send_message_to_user,
            report_infeasible_instructions=report_infeasible_instructions,
            agent_args=agent_args,
            env=sandbox_env,
        )

        time.sleep(0.3)
        try:
            sandbox_page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            try:
                sandbox_page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

        save_sandbox_screenshot(
            sandbox_page,
            action=action,
            ok=True,
            folder="photo",
        )

        result_state = extract_page_state(
            sandbox_page,
            fallback_obs=current_obs,
        )

        changed_meaningfully = page_changed_meaningfully(before_state, result_state)
        logger.info(f"sandbox action changed page meaningfully: {changed_meaningfully}")

        return {
            "ok": True,
            "action": action,
            "error": "",
            "state_before": before_state,
            "state_after": result_state,
            "changed_meaningfully": changed_meaningfully,
            "messages": captured_messages,
            "infeasible_messages": infeasible_messages,
            **rewrite_info,
        }

    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        return {
            "ok": False,
            "action": action,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
            "state_after": None,
            "messages": [],
            "infeasible_messages": [],
        }
    finally:
        if sandbox_context is not None:
            try:
                sandbox_context.close()
            except Exception:
                pass

def _to_jsonable(obj):
    try:
        import numpy as np
    except Exception:
        np = None

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]

    if np is not None:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()

    if hasattr(obj, "__dict__"):
        try:
            return _to_jsonable(vars(obj))
        except Exception:
            pass

    return repr(obj)

def summarize_obs_for_eval(obs: dict) -> dict:
    return {
        "last_action": _to_jsonable(obs.get("last_action", "")),
        "last_action_error": _to_jsonable(obs.get("last_action_error", "")),
        "open_pages_urls": _to_jsonable(obs.get("open_pages_urls", [])),
        "open_pages_titles": _to_jsonable(obs.get("open_pages_titles", [])),
        "active_page_index": _to_jsonable(obs.get("active_page_index", None)),
        "axtree_txt": _to_jsonable((obs.get("axtree_txt", "") or "")[:6000]),
        "chat_messages": _to_jsonable(obs.get("chat_messages", [])),
        "goal_object": _to_jsonable(obs.get("goal_object", [])),
    }


def build_evaluator_prompt(goal, current_state, candidate_action, next_state):
    goal = _to_jsonable(goal)
    current_state = _to_jsonable(current_state)
    next_state = _to_jsonable(next_state)

    return f"""
你是一个网页任务评估器。请评估一个候选动作是否让页面更接近用户目标。

# 用户目标
{json.dumps(goal, ensure_ascii=False, indent=2)}

# 当前状态
{json.dumps(current_state, ensure_ascii=False, indent=2)}

# 候选动作
{candidate_action}

# 候选动作执行后的状态
{json.dumps(next_state, ensure_ascii=False, indent=2)}

请判断：
1. 该动作执行后，是否更接近目标（true/false）
2. 该动作属于哪一类：
   - 有效推进
   - 无效探索
   - 错误偏航
3. 给出一个 0 到 10 的分数
4. 给出简短理由

只输出 JSON：
{{
  "closer_to_goal": true,
  "verdict": "有效推进",
  "score": 8.5,
  "reason": "..."
}}
"""


def _normalize_score(x: Any) -> float:
    try:
        score = float(x)
    except Exception:
        score = 0.0
    return max(0.0, min(10.0, score))


def evaluate_candidate_with_llm(
    client,
    model,
    goal,
    current_state,
    candidate_action,
    next_state,
):
    prompt = build_evaluator_prompt(goal, current_state, candidate_action, next_state)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "closer_to_goal": False,
            "verdict": "无效探索",
            "score": 0.0,
            "reason": f"invalid evaluator json: {raw[:500]}",
        }

    return {
        "closer_to_goal": bool(data.get("closer_to_goal", False)),
        "verdict": data.get("verdict", "无效探索"),
        "score": _normalize_score(data.get("score", 0.0)),
        "reason": data.get("reason", ""),
        "raw": raw,
        "prompt": prompt,
    }


def _extract_action(cand):
    if isinstance(cand, dict):
        return cand.get("action")
    if isinstance(cand, str):
        return cand
    return None


def select_best_action(env, agent, current_obs, candidates):
    """
    Returns:
        best_action, selection_info
    """
    current_state = summarize_obs_for_eval(current_obs)
    goal = current_obs.get("goal_object", [])

    filtered = []
    selection_info = {
        "all_candidates": candidates,
        "sandbox_results": [],
        "evaluator_results": [],
        "skipped_risky_actions": [],
    }

    fallback_action = None
    if candidates:
        fallback_action = _extract_action(candidates[0])

    for cand in candidates:
        action = _extract_action(cand)
        if not action:
            selection_info["sandbox_results"].append({
                "ok": False,
                "action": None,
                "error": "invalid candidate format",
            })
            continue

        if not is_safe_for_sandbox(action):
            selection_info["skipped_risky_actions"].append(action)
            continue

        sandbox_result = try_action_on_sandbox(
            env=env,
            action=action,
            current_obs=current_obs,
        )
        selection_info["sandbox_results"].append(sandbox_result)

        if not sandbox_result["ok"]:
            print("Not OK!")
            continue

        if sandbox_result.get("infeasible_messages"):
            continue

        if not sandbox_result.get("changed_meaningfully", False):
            continue

        try:
            eval_result = evaluate_candidate_with_llm(
                client=agent.client,
                model=MY_MODEL,
                goal=goal,
                current_state=current_state,
                candidate_action=action,
                next_state=sandbox_result["state_after"],
            )
        except Exception as e:
            eval_result = {
                "closer_to_goal": False,
                "verdict": "无效探索",
                "score": 0.0,
                "reason": f"evaluator failed: {type(e).__name__}: {e}",
                "raw": "",
                "prompt": "",
            }
        print(f'{eval_result["verdict"]}, {eval_result["score"]}, {eval_result["reason"]}')
        merged = {
            "action": action,
            "sandbox": sandbox_result,
            "evaluation": eval_result,
        }
        filtered.append(merged)
        selection_info["evaluator_results"].append(merged)

    if not filtered:
        selection_info["selected_action"] = fallback_action
        selection_info["fallback_reason"] = "no candidate survived sandbox/evaluator"
        return fallback_action, selection_info

    filtered.sort(key=lambda x: x["evaluation"]["score"], reverse=True)
    best = filtered[0]["action"]
    selection_info["selected_action"] = best
    selection_info["ranked_actions"] = [
        {
            "action": item["action"],
            "score": item["evaluation"]["score"],
            "verdict": item["evaluation"]["verdict"],
            "reason": item["evaluation"]["reason"],
        }
        for item in filtered
    ]

    return best, selection_info