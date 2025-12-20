import json
import subprocess
import sys
import time
import random
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 配置 ---
TASK_JSON_PATH = "gitlab_tasks_final_v12.json"
AGENT_SCRIPT = "run_single_task.py"
MEMORY_DIR = "memory"
LLM_MODEL = "deepseek-chat"
MAX_WORKERS = 2  # 【新增】并发数量，根据你的 API 限流情况调整

# URL 映射
URL_MAPPING = {
    "__GITLAB__": "http://172.26.116.102:8080",
    "__REDDIT__": "http://127.0.0.1:9999",
    "__SHOPPING__": "http://127.0.0.1:7770",
    "__WIKIPEDIA__": "http://127.0.0.1:8888",
    "__MAP__": "http://127.0.0.1:3000"
}

def clean_memory():
    """清空之前的记忆"""
    path = Path(MEMORY_DIR)
    if path.exists():
        print("🧹 Cleaning old memory...")
        # shutil.rmtree(path) 
        pass
    path.mkdir(exist_ok=True)

def replace_urls(text):
    if not text: return ""
    for key, value in URL_MAPPING.items():
        text = text.replace(key, value)
    return text

def process_single_task_wrapper(task_conf, mode, index, total):
    """
    单个任务的执行逻辑，将被线程池调用
    """
    task_id = task_conf.get("task_id")
    task_name = f"task_{task_id}"
    raw_intent = task_conf.get("intent", "")
    raw_url = task_conf.get("start_url", "")
    
    intent = replace_urls(raw_intent)
    start_url = replace_urls(raw_url)
    
    # 简单的日志前缀，用于区分不同线程的输出（可选：也可以完全静默 subprocess）
    print(f"🚀 [Start] {task_name} ({index}/{total})")
    
    cmd = [
        sys.executable, AGENT_SCRIPT,
        "--task_name", task_name,
        "--task", intent,
        "--start_url", start_url,
        "--mode", mode,
        "--llm", LLM_MODEL
    ]
    
    try:
        # capture_output=True 可以防止子进程输出打乱主进程进度条，
        # 但如果想实时看 Log，可以设为 False
        subprocess.run(cmd, check=False, capture_output=True) 
    except Exception as e:
        print(f"❌ Error running {task_name}: {e}")

    # 读取该任务的结果
    # 注意：路径必须与 run_single_task.py 中的 output_dir 逻辑一致
    res_path = Path("outputs") / task_name / "result.json"
    
    result = {"task_id": task_name, "success": False, "status": "FAILED"}
    
    if res_path.exists():
        try:
            with open(res_path, "r", encoding="utf-8") as f:
                result = json.load(f)
        except Exception as e:
            print(f"⚠️ Read result failed for {task_name}: {e}")
    else:
        print(f"⚠️ No result file found for {task_name}")
            
    return result

def run_task_batch(tasks, mode):
    """并行运行一批任务"""
    results = []
    total = len(tasks)
    
    print(f"\n{'='*20} STARTING {mode.upper()} PHASE ({total} tasks) with {MAX_WORKERS} workers {'='*20}")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(process_single_task_wrapper, task, mode, i+1, total): task 
            for i, task in enumerate(tasks)
        }
        
        # 收集结果
        for future in as_completed(future_to_task):
            try:
                res = future.result()
                results.append(res)
                # 打印简单的进度反馈
                symbol = "✅" if res.get("success") else "❌"
                print(f"{symbol} [Done] {res.get('task_id')}")
            except Exception as exc:
                print(f"Generated an exception: {exc}")

    return results

def main():
    mode = 'train' # 或 'test'

    if not Path(TASK_JSON_PATH).exists():
        print("Error: task.json not found.")
        # 创建一个伪造的 task.json 用于测试
        with open(TASK_JSON_PATH, "w") as f:
            json.dump([{"task_id": i, "intent": f"test task {i}", "start_url": "__GITLAB__"} for i in range(10)], f)
        print("Created dummy task.json for testing.")

    with open(TASK_JSON_PATH, "r", encoding="utf-8") as f:
        all_tasks = json.load(f)
    
    all_tasks = all_tasks[0:2]
    print(f"📊 Dataset Split: Total={len(all_tasks)}")

    if mode == 'train':
        clean_memory()
        train_results = run_task_batch(all_tasks, "train")
        train_success = sum(1 for r in train_results if r.get("success"))
        print(f"\n🧠 Training Phase Complete. Success: {train_success}/{len(all_tasks)}")

    else:
        test_results = run_task_batch(all_tasks, "test")
        test_success = sum(1 for r in test_results if r.get("success"))
        accuracy = test_success / len(all_tasks) * 100 if len(all_tasks) > 0 else 0
        
        print(f"\n{'='*50}")
        print(f"🏆 FINAL BENCHMARK REPORT")
        print(f"Test Accuracy:  {accuracy:.2f}%")
        
        with open("final_report.json", "w") as f:
            json.dump({
                "test_results": test_results,
                "accuracy": accuracy
            }, f, indent=4)

if __name__ == "__main__":
    main()