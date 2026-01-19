import os
import sys
import json
import asyncio
import argparse
import traceback
from pathlib import Path
import threading

# Assuming these exist in your project structure
from agent import MUSE
from prompt.system_prompt import MUSE_sys_prompt

def init_empty_memory_files(output_dir: Path):
    """
    在输出目录创建三个空的记忆文件
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    memory_files = [
        "procedural_memory.json",
        "strategic_memory.json", 
        "tool_memory.json"
    ]
    
    for filename in memory_files:
        file_path = output_dir / filename
        # 如果文件不存在，或者你想强制覆盖为空，请去掉 if not file_path.exists() 判断
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent_name", type=str, default="muse_bot")
    parser.add_argument("--task_name", type=str, required=True)
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--mode", type=str, required=True)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--llm", type=str, default="deepseek-chat")
    parser.add_argument("--start_url", type=str, default="")
    args = parser.parse_args()
    
    # 1. Setup Directories immediately
    output_dir = Path("outputs") / args.task_name
    output_dir.mkdir(parents=True, exist_ok=True) # Critical: Create dir before logic starts
    thread_id = threading.get_ident()
    memory_dir = Path("memory") / str(thread_id)

    init_empty_memory_files(memory_dir)

    # Default Result State
    result_data = {
        "task_id": args.task_name,
        "success": False,
        "mode": args.mode,
        "actions": 0,
        "error_msg": None
    }

    print(f"🚀 [Task Start] {args.task_name} | Mode: {args.mode}")

    try:
        use_mem = True  
        update_mem = True if args.mode == "train" else False

        agent = MUSE(
            init_model_name=args.llm,
            sys_prompt_template=MUSE_sys_prompt,
            memory_dir=str(memory_dir), 
            agent_name=args.agent_name,
            task_name=args.task_name,
            output_dir=str(output_dir), 
            mode_label=args.mode,
            task_round=args.round,
            use_memory=use_mem,
            update_memory=update_mem
        )

        auth_info = (
            f"\n\n[Available Credentials]\n"
            f"If authentication is required, use the following:\n"
            f"Username: byteblaze\n"
            f"Password: a_very_secure_password_123!"
        )
        full_prompt = f"Task Goal: {args.task}\n\nTarget Website URL: {args.start_url}{auth_info}"
        
        # Run Agent
        await agent.run(full_prompt, subtask_action_limit=5, time_limit=2400, verbose=False)

        # Check Success Criteria
        is_success = False
        if not agent.to_do_subtasks and agent.monitor.done_subtasks:
            if agent.monitor.done_subtasks[-1].finish:
                is_success = True
        
        result_data["success"] = is_success
        result_data["actions"] = agent.monitor.num_actions
        result_data["status"] = "COMPLETED"
        
        print(f"🏁 [Task End] {args.task_name}: {'✅ SUCCESS' if is_success else '❌ FAILURE'}")

    except Exception as e:
        # Catch any crash during agent execution
        error_trace = traceback.format_exc()
        print(f"❌ [Task Crash] {args.task_name}: {e}")
        print(error_trace)
        
        result_data["success"] = False
        result_data["status"] = "CRASHED"
        result_data["error_msg"] = str(e)
        result_data["traceback"] = error_trace

    finally:
        # Always save result.json, even on crash
        try:
            with open(output_dir / "result.json", "w", encoding="utf-8") as f:
                json.dump(result_data, f, indent=4)
        except Exception as write_err:
            print(f"🔥 Critical: Could not write result.json: {write_err}")

if __name__ == "__main__":
    asyncio.run(main())