import os
import json
import asyncio
import argparse
from pathlib import Path

from agent import MUSE
from prompt.system_prompt import MUSE_sys_prompt

# 确保 memory 目录存在
MEMORY_DIR = Path("memory")
MEMORY_DIR.mkdir(exist_ok=True)

async def main():
    parser = argparse.ArgumentParser(description="MUSE Pipeline Runner")
    parser.add_argument("--agent_name", type=str, default="muse_bot")
    parser.add_argument("--task_name", type=str, required=True)
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--mode", type=str, required=True, choices=["train", "test"])
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--llm", type=str, default="deepseek-chat")
    parser.add_argument("--start_url", type=str, default="")
    
    args = parser.parse_args()

    # 配置逻辑：
    # Train 模式: 使用记忆 + 更新记忆 (边做边学)
    # Test  模式: 使用记忆 + 不更新记忆 (只考不学)
    
    use_mem = True  
    update_mem = True if args.mode == "train" else False

    print(f"🔄 Mode: {args.mode.upper()} | Use Memory: {use_mem} | Update Memory: {update_mem}")

    agent = MUSE(
        init_model_name=args.llm,
        sys_prompt_template=MUSE_sys_prompt,
        memory_dir=str(MEMORY_DIR), # 指向同一个记忆文件夹
        agent_name=args.agent_name,
        task_name=args.task_name,
        output_dir="outputs",
        mode_label=args.mode,
        task_round=args.round,
        use_memory=use_mem,
        update_memory=update_mem
    )

    full_prompt = f"Task Goal: {args.task}\n\nTarget Website URL: {args.start_url}"
    
    agent.logger.log_task(full_prompt, subtitle=f"{args.mode.upper()} PHASE", title=f"Task: {args.task_name}")
    
    action_limit = 20
    
    await agent.run(full_prompt, subtask_action_limit=action_limit, time_limit=2400, verbose=False)

    # --- 结果判定 (基于 Agent 自我认知) ---
    is_success = False
    if not agent.to_do_subtasks and agent.monitor.done_subtasks:
        if agent.monitor.done_subtasks[-1].finish:
            is_success = True
    
    result_data = {
        "task_id": args.task_name,
        "success": is_success,
        "mode": args.mode,
        "actions": agent.monitor.num_actions
    }

    # 输出结果
    output_path = agent._get_output_dir()
    output_path.mkdir(parents=True, exist_ok=True)
    with open(output_path / "result.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=4)
    
    print(f"[{args.mode.upper()}] Task {args.task_name}: {'✅ SUCCESS' if is_success else '❌ FAILURE'}")

if __name__ == "__main__":
    asyncio.run(main())