import json
import subprocess
import sys
import time
import random
import shutil
from pathlib import Path

# --- 配置 ---
TASK_JSON_PATH = "gitlab_tasks_final.json"
AGENT_SCRIPT = "run_single_task.py"
MEMORY_DIR = "memory"
LLM_MODEL = "deepseek-chat"

# URL 映射 (根据你的 WebArena 部署修改)
URL_MAPPING = {
    "__GITLAB__": "http://172.26.116.102:8080",
    "__REDDIT__": "http://127.0.0.1:9999",
    "__SHOPPING__": "http://127.0.0.1:7770",
    "__WIKIPEDIA__": "http://127.0.0.1:8888",
    "__MAP__": "http://127.0.0.1:3000"
}

def clean_memory():
    """清空之前的记忆，确保从零开始训练"""
    path = Path(MEMORY_DIR)
    if path.exists():
        print("🧹 Cleaning old memory...")
        # 注意：如果你想保留以前训练好的记忆，请注释掉这一行
        # shutil.rmtree(path) 
        pass
    path.mkdir(exist_ok=True)

def replace_urls(text):
    if not text: return ""
    for key, value in URL_MAPPING.items():
        text = text.replace(key, value)
    return text

def run_task_batch(tasks, mode):
    """运行一批任务"""
    results = []
    total = len(tasks)
    
    print(f"\n{'='*20} STARTING {mode.upper()} PHASE ({total} tasks) {'='*20}")
    
    for i, task_conf in enumerate(tasks):
        task_id = task_conf.get("task_id")
        task_name = f"task_{task_id}"
        raw_intent = task_conf.get("intent", "")
        raw_url = task_conf.get("start_url", "")
        
        intent = replace_urls(raw_intent)
        start_url = replace_urls(raw_url)
        
        print(f"\n▶️ [{mode.upper()}] {i+1}/{total} | ID: {task_id} | Intent: {intent[:50]}...")
        
        cmd = [
            sys.executable, AGENT_SCRIPT,
            "--task_name", task_name,
            "--task", intent,
            "--start_url", start_url,
            "--mode", mode,
            "--llm", LLM_MODEL
        ]
        
        try:
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"❌ Error running {task_name}: {e}")

        # 读取该任务的结果
        res_path = Path("outputs") / "muse_bot" / mode / task_name / "round_1" / "result.json"
        if res_path.exists():
            with open(res_path, "r") as f:
                results.append(json.load(f))
        else:
            results.append({"task_id": task_name, "success": False, "status": "CRASHED"})
            
    return results

def main():
    mode = 'test'

    # 1. 准备数据
    if not Path(TASK_JSON_PATH).exists():
        print("Error: task.json not found.")
        return

    with open(TASK_JSON_PATH, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)
    
    print(f"📊 Dataset Split: Total={len(all_tasks)}")

    if mode == 'train':
        # 2. 初始化记忆环境
        clean_memory()
        
        # 3. 训练阶段 (Training Phase)
        # Agent 在此阶段会写入 memory/tool_memory.json 等文件
        train_results = run_task_batch(all_tasks, "train")
        
        train_success = sum(1 for r in train_results if r.get("success"))
        print(f"\n🧠 Training Phase Complete. Success: {train_success}/{len(all_tasks)}")
        print("💾 Memory updated based on training tasks.")

    else:
        # 4. 测试阶段 (Testing Phase)
        # Agent 读取 memory/ 文件夹中的经验，但不进行写入
        test_results = run_task_batch(all_tasks, "test")
        
        # 5. 最终报告
        test_success = sum(1 for r in test_results if r.get("success"))
        accuracy = test_success / len(all_tasks) * 100
        
        print(f"\n{'='*50}")
        print(f"🏆 FINAL BENCHMARK REPORT")
        print(f"{'='*50}")
        print(f"Test Success:   {test_success}")
        print(f"Test Accuracy:  {accuracy:.2f}%")
        
        # 保存汇总结果
        with open("final_report.json", "w") as f:
            json.dump({
                "train_results": train_results,
                "test_results": test_results,
                "accuracy": accuracy
            }, f, indent=4)

if __name__ == "__main__":
    main()