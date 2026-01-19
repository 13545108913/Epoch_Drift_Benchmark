
import subprocess
import json
import traceback
import shlex

# ========================================================================
# Config
# ========================================================================
STATUS_EXECUTED = "COMMAND_EXECUTED"
STATUS_FAILURE_UNSAFE = "TOOL_FAILURE_UNSAFE_COMMAND"
STATUS_FAILURE_TIMEOUT = "TOOL_FAILURE_TIMEOUT"
STATUS_FAILURE_NOT_FOUND = "TOOL_FAILURE_COMMAND_NOT_FOUND"
STATUS_FAILURE_PARSING = "TOOL_FAILURE_PARSING_ERROR"
STATUS_FAILURE_EXCEPTION = "TOOL_FAILURE_UNKNOWN_EXCEPTION"

DANGEROUS_KEYWORDS = {"shutdown", "reboot", "poweroff", "halt"}
COMMAND_CATEGORIES = {
    "long_running": {
        "keywords": {"ping", "ping6", "top", "htop", "watch", "tail", "journalctl",
                     "tcpdump", "iftop", "nload", "yes"},
        "timeout": 20
    },
    "download": {
        "keywords": {"wget", "curl", "aria2c", "pip", "apt-get", "apt", "poetry",
                     "npm", "yarn", "pnpm", "composer", "gem", "bundle", "conda",
                     "cargo", "mvn", "gradle"},
        "timeout": 600
    }
}
DEFAULT_TIMEOUT = 270
MAX_OUTPUT_LENGTH = 65536

# ========================================================================
# Helpers
# ========================================================================
def _truncate_with_status(text: str, max_len: int) -> tuple[str, bool]:
    if len(text) > max_len:
        return text[:max_len], True
    return text, False

def _analyze_command(command: str) -> tuple[bool, str | None, int, str]:
    """
    Analyze raw command string:
      - Check dangerous keywords
      - Decide timeout
      - Handle sudo
    """
    try:
        tokens = shlex.split(command)
    except Exception as e:
        return False, f"❌ Command parsing error: {e}", 0, command

    if not tokens:
        return False, "❌ Error: command cannot be empty.", 0, command

    # Handle sudo: drop it
    warning_msg = None
    if tokens[0] == "sudo":
        if len(tokens) == 1:
            return False, "❌ Error: 'sudo' detected but no command provided after it.", 0, command
        tokens = tokens[1:]
        warning_msg = "ℹ️ You are root, 'sudo' is not required. It has been removed automatically."
        command = " ".join(tokens)

    command_head = tokens[0]
    if command_head in DANGEROUS_KEYWORDS:
        return False, f"❌ Error: command '{command_head}' is not allowed.", 0, command

    timeout = DEFAULT_TIMEOUT
    for category, config in COMMAND_CATEGORIES.items():
        if command_head in config["keywords"]:
            timeout = config["timeout"]
            msg = ""
            if category == "long_running":
                msg = f"⚠️ Detected long-running command '{command_head}'. Timeout is set to {timeout} seconds."
            elif category == "download":
                msg = f"⚠️ Detected download command '{command_head}'. Timeout is set to {timeout} seconds."
            warning_msg = (warning_msg + "\n" + msg) if warning_msg else msg
            break

    return True, warning_msg, timeout, command

# ========================================================================
# Main
# ========================================================================
async def run_cmd(command: str):
    """
    Execute a shell command

    Args:
        command: shell command string.
    """
    inner_result = {}

    try:
        is_safe, warning_msg, timeout_value, final_command = _analyze_command(command)
        if not is_safe:
            inner_result = {
                "execution_status": STATUS_FAILURE_UNSAFE,
                "stderr": warning_msg
            }
            yield {"data": json.dumps(inner_result, ensure_ascii=False, indent=2), "instruction": ""}
            return

        # Run command inside bash
        proc = subprocess.run(
            final_command,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="workspace",
            timeout=timeout_value
        )

        stdout, stdout_truncated = _truncate_with_status(proc.stdout.strip(), MAX_OUTPUT_LENGTH)
        stderr, stderr_truncated = _truncate_with_status(proc.stderr.strip(), MAX_OUTPUT_LENGTH)

        inner_result = {
            "execution_status": STATUS_EXECUTED,
            "command_result": {
                "executed_command": final_command,
                "returncode": proc.returncode,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
                "warning": warning_msg
            },
            "stdout": stdout,
            "stderr": stderr
        }

    except subprocess.TimeoutExpired:
        inner_result = {
            "execution_status": STATUS_FAILURE_TIMEOUT,
            "stderr": f"⏰ Command execution timed out (>{timeout_value} seconds). Process was terminated."
        }

    except FileNotFoundError:
        inner_result = {
            "execution_status": STATUS_FAILURE_NOT_FOUND,
            "stderr": f"❌ Command execution failed: '{command}' not found."
        }

    except Exception:
        inner_result = {
            "execution_status": STATUS_FAILURE_EXCEPTION,
            "stderr": f"⚠️ Unknown exception occurred:\n{traceback.format_exc(limit=2)}"
        }

    yield {"data": json.dumps(inner_result, ensure_ascii=False, indent=2), "instruction": ""}
