import os
import json
import argparse
import subprocess
from subprocess import Popen
import concurrent.futures
import threading

# 用于防止多线程print输出混乱
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def parse_task_ids(task_id_str: str) -> list[str]:
    chunks = [c.strip() for c in task_id_str.split(",")]
    task_id_list = []
    for c in chunks:
        s, e = [int(n.strip()) for n in c.split("-")]
        task_id_list.extend([str(i) for i in range(s, e+1)])
    return task_id_list

# 将单个任务的处理逻辑提取出来
def process_single_task(tid, website):
    try:
        # step 1: task solving
        # 注意：这里去掉了 input() 阻塞，因为并行时无法交互
        process = Popen([
            "python", "run_demo.py",
            "--task_name", f"myBenchmark.{tid}",
            "--websites", website,
            "--rename_to", f"myBenchmark.{tid}",
            "--headless"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) # 建议加上 text=True 以便直接处理字符串
        
        try:
            stdout, stderr = process.communicate(timeout=3000)
            safe_print(f"[{tid}] Step 1 completed successfully.")
            # safe_print(stdout) # 输出可能太长，建议根据需要开启
        except subprocess.TimeoutExpired as e:
            process.kill()
            stdout, stderr = process.communicate() # Clean up resources
            safe_print(f"[{tid}] Process timed out after {e.timeout} seconds.")
            safe_print(stderr)
            return # 相当于原来的 continue

        path = f"results/myBenchmark.{tid}/summary_info.json"
        if not os.path.exists(path):
            safe_print(f"[{tid}] Result file not found: {path}")
            return

        if json.load(open(path, 'r'))["n_steps"] < 3: 
            safe_print(f"[{tid}] Skipped due to n_steps < 3")
            return

        # step 2: eval traj
        process = Popen([
            "python", "-m", "autoeval.evaluate_trajectory",
            "--result_dir", f"results/myBenchmark.{tid}",
        ])
        process.wait()
        
        path = f"results/myBenchmark.{tid}/deepseek-chat_autoeval.json"
        if not os.path.exists(path):
            return
            
        is_correct = json.load(open(path))[0]["rm"]  # bool
        if not is_correct: 
            safe_print(f"[{tid}] Evaluation failed (rm=False)")
            return

        process = Popen([
            "python", "-m", "results.calc_valid_steps",
            "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
        ])
        process.wait()  # output 'clean_steps.json'

        # step 3: induce actions
        process = Popen([
            "python", "-m", "induce.induce_actions",
            "--website", website,
            "--result_id_list", tid,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        try:
            stdout, stderr = process.communicate(timeout=1000)
            safe_print(f"[{tid}] All steps completed.")
            # safe_print(stdout)
        except subprocess.TimeoutExpired as e:
            process.kill()
            stdout, stderr = process.communicate() 
            safe_print(f"[{tid}] Step 3 timed out.")
            safe_print(stderr)

    except Exception as e:
        safe_print(f"[{tid}] An error occurred: {e}")

# %% ASI
def run_asi_parallel(args):
    task_id_list = parse_task_ids(args.task_ids)
    total_tasks = len(task_id_list)
    print(f"Starting processing {total_tasks} tasks with {args.workers} workers...")

    # 使用 ThreadPoolExecutor 因为这是调用子进程（IO密集型），不需要 ProcessPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        # 提交所有任务
        futures = {executor.submit(process_single_task, tid, args.website): tid for tid in task_id_list}
        
        # 等待完成并在完成后获取结果（如果有报错会在这里抛出）
        for future in concurrent.futures.as_completed(futures):
            tid = futures[future]
            try:
                future.result() # 这里会捕获函数内的异常
            except Exception as exc:
                safe_print(f"Task {tid} generated an exception: {exc}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "admin", "reddit", "gitlab", "map"])
    parser.add_argument("--task_ids", type=str, required=True,
                        help="xxx-xxx,xxx-xxx")
    # 新增 workers 参数，默认设为 4，根据机器性能调整
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel workers (default: 4)")

    args = parser.parse_args()
    run_asi_parallel(args)
    