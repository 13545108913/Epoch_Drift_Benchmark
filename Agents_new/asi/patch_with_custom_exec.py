import re
import time
import datetime
import os  # 新增引用：用于获取进程ID

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
    Executes Python code in a new context.
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
    Step function with multiprocessing-safe error logging.
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
        
        # --- [Error Logging - Multiprocessing Safe] ---
        try:
            # 获取当前进程ID
            pid = os.getpid()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 构造日志内容，包含 PID 以便追踪
            log_entry = (
                f"[{timestamp}] [Process: {pid}] ERROR OCCURRED:\n"
                f"Action Code: {action}\n"
                f"Error Message: {self.last_action_error}\n"
                f"{'-'*50}\n"
            )
            
            # 使用包含 PID 的文件名，确保每个进程写自己的文件，避免冲突
            # 文件名示例: execution_errors_pid_12345.log
            log_filename = f"my_log/execution_errors_pid_{pid}.log"
            
            with open(log_filename, "a", encoding="utf-8") as f:
                f.write(log_entry)
                
        except Exception as log_err:
            logger.error(f"Failed to save error to local file: {log_err}")
        # --- [End of Error Logging] ---

        match = re.match("TimeoutError: Timeout ([0-9]+)ms exceeded.", self.last_action_error)
        if match:
            info["action_exec_timeout"] = float(match.groups()[0]) / 1000  # ms to sec
            
    logger.debug(f"Action executed")
    info["action_exec_stop"] = time.time()

    # wait a bit
    time.sleep(0.5) 
    self.context.cookies() 
    self._wait_dom_loaded()
    self._active_page_check()
    logger.debug(f"Active page checked")

    self._wait_for_user_message()
    logger.debug(f"User message done")

    logger.debug(f"Initiating task validation")
    reward, done, user_message, task_info = self._task_validate()
    info["task_info"] = task_info
    logger.debug(f"Task validation done")

    if user_message:
        self.chat.add_message(role="user", msg=user_message)

    obs = self._get_obs()
    logger.debug(f"Observation extracted")

    terminated = done or (
        self.terminate_on_infeasible and self.infeasible_message_received
    )
    truncated = False

    return obs, reward, terminated, truncated, info
    
def patch_with_custom_exec(args):
    global agent_args
    agent_args = args
    setattr(BrowserEnv, "step", step)