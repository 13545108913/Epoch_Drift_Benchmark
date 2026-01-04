import re
import time

import playwright.sync_api

from browsergym.core.env import BrowserEnv, logger


agent_args = None

def execute_python_code(
    code: str,
    page: playwright.sync_api.Page,
    send_message_to_user: callable,
    report_infeasible_instructions: callable,
    **additional_globals
):
    """
    Executes Python code in a new context, except for a playwright `page` object and a `send_message_to_user` function.

    WARNING: this is not safe!
    https://stackoverflow.com/questions/77655440/can-you-protect-a-python-variable-with-exec

    Args:
        code: the Python code to execute, as a string.
        page: the playwright page that will be made accessible to the code.
        send_message_to_user: utility function that will be made accessible to the code. It should take one text argument.
        report_infeasible_instructions: utility function that will be made accessible to the code. It should take one text argument.
        additional_globals: additional global variables to make accessible to the code.
    """

    globals = {
        "page": page,
        "send_message_to_user": send_message_to_user,
        "report_infeasible_instructions": report_infeasible_instructions,
        **additional_globals,
    }

    exec(code, globals)


def step(self: BrowserEnv, action: str) -> tuple:
    """
    Small modification of the original BrowserEnv step method that uses the custom 
    execute_python_code function. 
    TODO: Probably better to refactor browsergym to support custom exec instead of this hack.
    """        
    self.last_action = action

    info = {}
    info["action_exec_start"] = time.time()
    info["action_exec_timeout"] = 0

    def send_message_to_user(text: str):
        if not isinstance(text, str):
            raise ValueError(f"Forbidden value: {text} is not a string")
        self.chat.add_message(role="assistant", msg=text)

    def report_infeasible_instructions(reason: str):
        if not isinstance(reason, str):
            raise ValueError(f"Forbidden value: {reason} is not a string")
        self.chat.add_message(role="infeasible", msg=reason)
        self.infeasible_message_received = True

    # try to execute the action
    logger.debug(f"Executing action")
    try:
        if self.action_mapping:
            code = self.action_mapping(action)
        else:
            code = action
        execute_python_code(
            code,
            self.page,
            send_message_to_user=send_message_to_user,
            report_infeasible_instructions=report_infeasible_instructions,
            agent_args=agent_args,
            env=self,
        )
        self.last_action_error = ""
    except Exception as e:
        self.last_action_error = f"{type(e).__name__}: {e}"
        match = re.match("TimeoutError: Timeout ([0-9]+)ms exceeded.", self.last_action_error)
        if match:
            info["action_exec_timeout"] = float(match.groups()[0]) / 1000  # ms to sec
    logger.debug(f"Action executed")
    info["action_exec_stop"] = time.time()

    # wait a bit (for the JavaScript callback to set the active page)
    time.sleep(0.5)  # wait for JS events to be fired (half a second)
    self.context.cookies()  # trigger all waiting Playwright callbacks on the stack (hack, see https://playwright.dev/java/docs/multithreading)

    # wait for the network to idle before extracting the observation, reward etc.
    self._wait_dom_loaded()

    # after the action is executed, the active page might have changed
    # perform a safety check
    self._active_page_check()
    logger.debug(f"Active page checked")

    # if asked, wait for user message
    self._wait_for_user_message()
    logger.debug(f"User message done")

    logger.debug(f"Initiating task validation")
    # extract reward, done, user_message, info (task-specific)
    reward, done, user_message, task_info = self._task_validate()
    info["task_info"] = task_info
    logger.debug(f"Task validation done")

    # add any user message sent by the task to the chat
    if user_message:
        self.chat.add_message(role="user", msg=user_message)

    # extract observation (generic)
    obs = self._get_obs()
    logger.debug(f"Observation extracted")

    # new step API wants a 5-tuple (gymnasium)
    terminated = done or (
        self.terminate_on_infeasible and self.infeasible_message_received
    )  # task or agent can terminate the episode
    truncated = False

    return obs, reward, terminated, truncated, info
    
def patch_with_custom_exec(args):
    global agent_args
    agent_args = args
    setattr(BrowserEnv, "step", step)