import base64
import dataclasses
import io
import os
import openai
import logging
import json

import numpy as np
from PIL import Image

from browsergym.experiments import AbstractAgentArgs, Agent
from browsergym.utils.obs import flatten_axtree_to_str, flatten_dom_to_str, prune_html

from custom_action_set import CustomActionSet
from actions import ACTION_DICT

logger = logging.getLogger(__name__)

MY_API_KEY = os.getenv("my_api_key")
MY_BASE_URL = os.getenv("my_base_url")
MY_MODEL = os.getenv("my_model")


def image_to_jpg_base64_url(image: np.ndarray | Image.Image):
    """Convert a numpy array to a base64 encoded image url."""
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    if image.mode in ("RGBA", "LA"):
        image = image.convert("RGB")

    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/jpeg;base64,{image_base64}"


class DemoAgent(Agent):
    """A basic agent using OpenAI API, to demonstrate BrowserGym's functionalities."""

    def obs_preprocessor(self, obs: dict) -> dict:
        return {
            "chat_messages": obs["chat_messages"],
            "screenshot": obs["screenshot"],
            "goal_object": obs["goal_object"],
            "last_action": obs["last_action"],
            "last_action_error": obs["last_action_error"],
            "open_pages_urls": obs["open_pages_urls"],
            "open_pages_titles": obs["open_pages_titles"],
            "active_page_index": obs["active_page_index"],
            "axtree_txt": flatten_axtree_to_str(obs["axtree_object"]),
            "pruned_html": prune_html(flatten_dom_to_str(obs["dom_object"])),
        }

    def __init__(
        self,
        model_name: str,
        chat_mode: bool,
        demo_mode: str,
        use_html: bool,
        use_axtree: bool,
        use_screenshot: bool,
        websites: tuple[str],
        actions: list[str],
        memory: str,
        output_dir: str,
        task_name: str,
        candidate_k: int = 3,
    ) -> None:
        super().__init__()
        self.model_name = model_name
        self.chat_mode = chat_mode
        self.use_html = use_html
        self.use_axtree = use_axtree
        self.use_screenshot = use_screenshot
        self.task_name = task_name or "task"
        self.output_dir = output_dir or "."
        self.candidate_k = candidate_k
        os.makedirs(self.output_dir, exist_ok=True)

        self.client = openai.OpenAI(
            api_key=MY_API_KEY,
            base_url=MY_BASE_URL,
        )

        if not (use_html or use_axtree):
            raise ValueError("Either use_html or use_axtree must be set to True.")

        custom_actions = ACTION_DICT["general"] + ACTION_DICT["webarena"] + ACTION_DICT["gitlab"]

        self.action_set = CustomActionSet(
            subsets=["custom"],
            custom_actions=custom_actions,
            strict=False,       # less strict on the parsing of the actions
            multiaction=True,   # enable the agent to take multiple actions at once
            demo_mode=demo_mode,
        )

        self.action_history = []
        self.actions = actions
        self.num_actions = 0

        if memory is None:
            self.memory = None
        else:
            paths = memory.split(" ")
            self.memory = "\n\n".join([open(p, "r", encoding="utf-8").read() for p in paths])
            if self.memory.strip() == "":
                self.memory = None

    def _build_json_action_prompt(self, k: int) -> str:
        return f"""\
# Output Format

Do NOT output a direct executable action alone.
You MUST output a valid JSON object with exactly {k} candidate actions.

Requirements:
1. Output must be valid JSON only. No markdown fences.
2. You must return exactly {k} candidates in `candidates`.
3. Candidates may repeat the same action type with different parameters.
   For example, `click("226")` and `click("227")` can both appear.
4. Each candidate must contain:
   - `action`: the action string to be executed by the environment
   - `reason`: a short reason for why this is a good candidate
5. Rank candidates from best to worst.
6. The first candidate will be used as the default action to execute.
7. Keep each `reason` concise and grounded in the current observation.

Schema:
{{
  "candidates": [
    {{
      "action": "click(\\"12\\")",
      "reason": "The submit button with bid 12 is the most likely next step."
    }}
  ]
}}
"""

    def _extract_candidates_from_response(self, raw_content: str, k: int) -> list[dict]:
        """
        Parse LLM JSON response and return normalized candidates:
        [{"action": "...", "reason": "..."}, ...]
        """
        if not raw_content:
            return []

        text = raw_content.strip()

        # Be tolerant to accidental code fences
        if text.startswith("```"):
            text = (
                text.replace("```json", "")
                .replace("```python", "")
                .replace("```", "")
                .strip()
            )

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}; raw={raw_content}")
            return []

        candidates = data.get("candidates", [])
        if not isinstance(candidates, list):
            logger.error(f"Invalid candidates field in LLM response: {data}")
            return []

        normalized = []
        for item in candidates:
            if not isinstance(item, dict):
                continue

            action = item.get("action", "")
            reason = item.get("reason", "")

            if isinstance(action, str) and action.strip():
                normalized.append(
                    {
                        "action": '```' + action.strip() + '```',
                        "reason": reason.strip() if isinstance(reason, str) else "",
                    }
                )

        return normalized[:k]

    def _append_token_usage_log(self, response, step: int) -> None:
        if not getattr(response, "usage", None):
            return

        log_file_path = os.path.join(self.output_dir, f"{self.task_name}.json")

        token_info = {
            "step": step,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "model": response.model,
        }

        try:
            if os.path.exists(log_file_path):
                with open(log_file_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        if not isinstance(data, list):
                            data = []
                    except json.JSONDecodeError:
                        data = []
            else:
                data = []

            data.append(token_info)

            with open(log_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

        except Exception as io_err:
            logger.error(f"Failed to write token logs to {log_file_path}: {io_err}")

    def _save_llm_io_markdown(
        self,
        step: int,
        prompt_text: str,
        response_text: str,
        parsed_candidates: list[dict] | None = None,
    ) -> None:
        """
        Save the LLM input and output into a local markdown file.
        One file per step.
        """
        md_path = os.path.join(self.output_dir, f"{self.task_name}_step_{step:04d}.md")

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("# LLM Interaction Log\n\n")
                f.write(f"- task_name: `{self.task_name}`\n")
                f.write(f"- step: `{step}`\n")
                f.write(f"- model: `{MY_MODEL}`\n\n")

                f.write("## Input\n\n")
                f.write("```text\n")
                f.write(prompt_text if prompt_text else "")
                f.write("\n```\n\n")

                f.write("## Raw Output\n\n")
                f.write("```json\n")
                f.write(response_text if response_text else "")
                f.write("\n```\n\n")

                if parsed_candidates is not None:
                    f.write("## Parsed Candidates\n\n")
                    f.write("```json\n")
                    f.write(json.dumps(parsed_candidates, ensure_ascii=False, indent=2))
                    f.write("\n```\n")
        except Exception as e:
            logger.error(f"Failed to save markdown log to {md_path}: {e}")

    # def _format_action_history_item(self, executed_action: str, info: dict) -> str:
    #     if info.get("candidate_actions"):
    #         history_item = {
    #             "executed_action": executed_action,
    #             "candidate_actions": info["candidate_actions"],
    #         }
    #         return json.dumps(history_item, ensure_ascii=False)
    #     return executed_action

    def get_action(self, obs: dict) -> tuple[str, dict]:
        info = {}

        if len(self.actions) == 0 or (self.num_actions > (len(self.actions) - 1)):
            system_msgs = []
            user_msgs = []

            if self.chat_mode:
                system_msgs.append(
                    {
                        "type": "text",
                        "text": """\
# Instructions

You are a UI Assistant, your goal is to help the user perform tasks using a web browser. You can
communicate with the user via a chat, to which the user gives you instructions and to which you
can send back messages. You have access to a web browser that both you and the user can see,
and with which only you can interact via specific commands.

Review the instructions from the user, the current state of the page and all other information
to find the best possible next action to accomplish your goal. Your answer will be interpreted
and executed by a program, make sure to follow the formatting instructions.

If the page is blocked by a popup or overlay, prioritize closing it before taking other actions.
In particular, look for:
- a full-page overlay that blocks interaction,
- a modal/dialog floating above the page,
- a close button near the popup corner,
- controls labeled “X”, “✖”, “Close”, or similar dismiss text.

When such a blocking popup is detected, prefer clicking the close control first.
Only ignore the popup if it is necessary for completing the task.
""",
                    }
                )

                user_msgs.append(
                    {
                        "type": "text",
                        "text": """\
# Chat Messages
""",
                    }
                )
                for msg in obs["chat_messages"]:
                    if msg["role"] in ("user", "assistant", "infeasible"):
                        user_msgs.append(
                            {
                                "type": "text",
                                "text": f"""\
- [{msg['role']}] {msg['message']}
""",
                            }
                        )
                    elif msg["role"] == "user_image":
                        user_msgs.append({"type": "image_url", "image_url": msg["message"]})
                    else:
                        raise ValueError(f"Unexpected chat message role {repr(msg['role'])}")

            else:
                assert obs["goal_object"], "The goal is missing."
                system_msgs.append(
                    {
                        "type": "text",
                        "text": """\
# Instructions

Review the current state of the page and all other information to find the best
possible next action to accomplish your goal. Your answer will be interpreted
and executed by a program, make sure to follow the formatting instructions.

If the page is blocked by a popup or overlay, prioritize closing it before taking other actions.
In particular, look for:
- a full-page overlay that blocks interaction,
- a modal/dialog floating above the page,
- a close button near the popup corner,
- controls labeled “X”, “✖”, “Close”, or similar dismiss text.

When such a blocking popup is detected, prefer clicking the close control first.
Only ignore the popup if it is necessary for completing the task.
""",
                    }
                )

                if self.memory is not None:
                    system_msgs.append(
                        {
                            "type": "text",
                            "text": self.memory,
                        }
                    )

                user_msgs.append(
                    {
                        "type": "text",
                        "text": """\
# Goal
""",
                    }
                )
                user_msgs.extend(obs["goal_object"])

            user_msgs.append(
                {
                    "type": "text",
                    "text": """\
# Currently open tabs
""",
                }
            )
            for page_index, (page_url, page_title) in enumerate(
                zip(obs["open_pages_urls"], obs["open_pages_titles"])
            ):
                user_msgs.append(
                    {
                        "type": "text",
                        "text": f"""\
Tab {page_index}{" (active tab)" if page_index == obs["active_page_index"] else ""}
Title: {page_title}
URL: {page_url}
""",
                    }
                )

            if self.use_axtree:
                user_msgs.append(
                    {
                        "type": "text",
                        "text": f"""\
# Current page Accessibility Tree

{obs["axtree_txt"]}

""",
                    }
                )

            if self.use_html:
                user_msgs.append(
                    {
                        "type": "text",
                        "text": f"""\
# Current page DOM

{obs["pruned_html"]}

""",
                    }
                )

            if self.use_screenshot:
                user_msgs.append(
                    {
                        "type": "text",
                        "text": """\
# Current page Screenshot
""",
                    }
                )
                user_msgs.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_to_jpg_base64_url(obs["screenshot"]),
                            "detail": "auto",
                        },
                    }
                )

            user_msgs.append(
                {
                    "type": "text",
                    "text": f"""\
# Action Space

{self.action_set.describe(with_long_description=True, with_examples=True)}

When high-level functions such as `get_driving_time` or `book_flights` are available, please prioritize using them.
Actions must be represented as executable action strings, for example:
- click("12")
- send_msg_to_user("The price for a 15 inch laptop is 1499 USD.")

Do NOT output the action directly.
Instead, output JSON candidate actions according to the required schema.
""",
                }
            )

            if self.action_history:
                user_msgs.append(
                    {
                        "type": "text",
                        "text": """\
# History of past actions
""",
                    }
                )
                user_msgs.extend(
                    [
                        {
                            "type": "text",
                            "text": f"""\

{action}
""",
                        }
                        for action in self.action_history
                    ]
                )

                if obs["last_action_error"]:
                    user_msgs.append(
                        {
                            "type": "text",
                            "text": f"""\
# Error message from last action

{obs["last_action_error"]}

""",
                        }
                    )
                    print("Error message from last action: ", obs["last_action_error"])

            user_msgs.append(
                {
                    "type": "text",
                    "text": f"""\
# Next action

Reflect on your past actions, any resulting error message, and the current state of the page.
Before choosing the next action, check whether the page is being blocked by a popup, modal, or overlay.
If so, prioritize dismissing it by clicking its close control (such as “X”, “✖”, or “Close”) before other actions.
Then produce exactly {self.candidate_k} candidate actions in JSON format, ranked from best to worst.
The candidates may use the same action type with different parameters.
""",
                }
            )

            json_instruction = self._build_json_action_prompt(self.candidate_k)
            user_msgs.append(
                {
                    "type": "text",
                    "text": json_instruction,
                }
            )

            prompt_text_strings = []
            for message in system_msgs + user_msgs:
                match message["type"]:
                    case "text":
                        prompt_text_strings.append(message["text"])
                    case "image_url":
                        image_url = message["image_url"]
                        if isinstance(image_url, dict):
                            image_url = image_url["url"]
                        if isinstance(image_url, str) and image_url.startswith("data:image"):
                            prompt_text_strings.append(
                                "image_url: " + image_url[:30] + "... (truncated)"
                            )
                        else:
                            prompt_text_strings.append("image_url: " + str(image_url))
                    case _:
                        raise ValueError(
                            f"Unknown message type {repr(message['type'])} in the task goal."
                        )

            prompt_text = "\n\n".join(prompt_text_strings)

            try:
                response = self.client.chat.completions.create(
                    model=MY_MODEL,
                    messages=[
                        {"role": "system", "content": system_msgs},
                        {"role": "user", "content": user_msgs},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                raw_output = response.choices[0].message.content or ""
                candidates = self._extract_candidates_from_response(raw_output, self.candidate_k)

                if not candidates:
                    logger.error("LLM returned no valid candidate actions.")
                    action = ""
                    info = {
                        "candidate_actions": [],
                        "raw_llm_output": raw_output,
                    }
                else:
                    action = candidates[0]["action"]
                    info = {
                        "candidate_actions": candidates,
                        "raw_llm_output": raw_output,
                    }

                self._save_llm_io_markdown(
                    step=len(self.action_history),
                    prompt_text=prompt_text,
                    response_text=raw_output,
                    parsed_candidates=candidates,
                )

                self._append_token_usage_log(response, self.num_actions)

            except Exception as e:
                logger.error(f"Error calling API: {e}")
                action = ""
                info = {
                    "candidate_actions": [],
                    "raw_llm_output": "",
                    "error": str(e),
                }

                try:
                    self._save_llm_io_markdown(
                        step=self.num_actions,
                        prompt_text=prompt_text,
                        response_text=json.dumps({"error": str(e)}, ensure_ascii=False, indent=2),
                        parsed_candidates=[],
                    )
                except Exception:
                    pass
        else:
            if self.num_actions > (len(self.actions) - 1):
                action = None
            else:
                action = self.actions[self.num_actions]
            self.num_actions += 1
            info = {}

        # self.action_history.append(self._format_action_history_item(action, info))
        # self.action_history.append(action)

        return action, info


@dataclasses.dataclass
class DemoAgentArgs(AbstractAgentArgs):
    """
    This class is meant to store the arguments that define the agent.

    By isolating them in a dataclass, this ensures serialization without storing
    internal states of the agent.
    """

    model_name: str = "gpt-4o-mini"
    chat_mode: bool = False
    demo_mode: str = "off"
    use_html: bool = False
    use_axtree: bool = True
    use_screenshot: bool = False
    websites: tuple[str] = ()
    actions: list[str] = ()
    memory: str = None
    output_dir: str = None
    task_name: str = None
    candidate_k: int = 2

    def make_agent(self):
        return DemoAgent(
            model_name=self.model_name,
            chat_mode=self.chat_mode,
            demo_mode=self.demo_mode,
            use_html=self.use_html,
            use_axtree=self.use_axtree,
            use_screenshot=self.use_screenshot,
            websites=self.websites,
            actions=self.actions,
            memory=self.memory,
            output_dir=self.output_dir,
            task_name=self.task_name,
            candidate_k=self.candidate_k,
        )