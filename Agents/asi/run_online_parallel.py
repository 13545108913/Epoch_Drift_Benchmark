import os
import json
import argparse
import subprocess
import sys
from subprocess import Popen, PIPE, STDOUT
import multiprocessing
from functools import partial

# --- 原有的辅助函数保持不变 ---

def parse_task_ids(task_id_str: str) -> list[str]:
    chunks = [c.strip() for c in task_id_str.split(",")]
    task_id_list = []
    for c in chunks:
        s, e = [int(n.strip()) for n in c.split("-")]
        task_id_list.extend([str(i) for i in range(s, e+1)])
    return task_id_list

def count_deepseek_calls(log_output: str) -> int:
    if not log_output:
        return 0
    keyword = "HTTP Request: POST https://api.deepseek.com/chat/completions"
    return log_output.count(keyword)

def save_task_info(task_id, step1, step2, step3, step4):
    """保存统计结果到 JSON 文件"""
    total = step1 + step2 + step3 + step4
    info_str = f"Task [{task_id}]: Total {total} (step1_solve: {step1}, step2_eval: {step2}, step3_cal: {step3}, step4_induce: {step4})"
    
    os.makedirs("./llm_info", exist_ok=True)
    save_path = f"./llm_info/{task_id}.json"
    
    # 为了防止多进程同时写入同一个文件（虽然这里是按task_id分文件的，比较安全），
    # 但print输出混杂，这里建议只保留文件写入，减少print
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump({"result": info_str}, f, ensure_ascii=False, indent=2)
    
    # 在多进程中，print 可能会乱序，但为了监控还是保留
    print(f"\n>>> [STATS SAVED] {info_str}\n")

def run_process_and_count(cmd, env=None, task_prefix=""):
    """
    运行子进程。增加 task_prefix 用于区分不同进程的日志输出。
    """
    # 简单的格式化打印，避免多进程日志完全混在一起分不清
    cmd_str = ' '.join(cmd)
    # print(f"{task_prefix} Executing: {cmd_str}") 
    
    process = Popen(cmd, stdout=PIPE, stderr=STDOUT, env=env, text=True, encoding='utf-8', errors='replace')
    
    full_log = []
    try:
        for line in process.stdout:
            # 在多进程下，建议注释掉实时 print，或者加上前缀，否则屏幕会非常乱
            # print(f"{task_prefix} {line}", end='') 
            full_log.append(line)
        process.wait()
    except KeyboardInterrupt:
        print(f"\n{task_prefix} Stopping process...")
        process.kill()
        process.wait()
        raise
        
    full_log_str = "".join(full_log)
    count = count_deepseek_calls(full_log_str)
    return count, full_log_str

# --- 核心逻辑重构 ---

def process_single_task(tid, args, lock):
    """
    单个任务的处理逻辑。
    args: 命令行参数
    lock: 进程锁，用于保护 Step 4
    """
    task_prefix = f"[Task {tid}]"
    print(f"{task_prefix} Starting...")

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    s1 = s2 = s3 = s4 = 0
    
    # --- Step 1: Solving (并行执行) ---
    print(f"{task_prefix} Step 1: Solving(ASI)...")
    cmd1 = [
        "python", "run_demo.py",
        "--task_name", f"myBenchmark.{tid}",
        "--websites", args.website,
        "--rename_to", f"myBenchmark.{tid}",
        "--headless"
    ]
    s1, _ = run_process_and_count(cmd1, env, task_prefix)
    
    # 检查 Step 1 结果
    path = f"results/myBenchmark.{tid}/summary_info.json"
    if not os.path.exists(path):
        save_task_info(tid, s1, s2, s3, s4)
        return
    try:
        if json.load(open(path, 'r')).get("n_steps", 0) < 3: 
            save_task_info(tid, s1, s2, s3, s4)
            return
    except:
        pass

    # --- Step 2: Evaluating (并行执行) ---
    print(f"{task_prefix} Step 2: Evaluating...")
    cmd2 = [
        "python", "-m", "autoeval.evaluate_trajectory",
        "--result_dir", f"results/myBenchmark.{tid}",
    ]
    s2, _ = run_process_and_count(cmd2, env, task_prefix)
    
    # 检查 Eval 结果
    path_eval = f"results/myBenchmark.{tid}/deepseek-chat_autoeval.json"
    is_correct = False
    if os.path.exists(path_eval):
        try:
            data = json.load(open(path_eval))
            if data and isinstance(data, list):
                is_correct = data[0].get("rm", False)
        except:
            pass
    
    if not is_correct: 
        save_task_info(tid, s1, s2, s3, s4)
        return

    # --- Step 3: Calculation (并行执行) ---
    print(f"{task_prefix} Step 3: Calculating...")
    cmd3 = [
        "python", "-m", "results.calc_valid_steps",
        "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
    ]
    s3, _ = run_process_and_count(cmd3, env, task_prefix)

    # --- Step 4: Inducing (串行执行 - 加锁) ---
    # 这是关键点！induce_action.py 会修改共享文件，必须加锁
    print(f"{task_prefix} Step 4: Waiting for lock to Induce Actions...")
    
    with lock:
        print(f"{task_prefix} >>> Acquired Lock. Running Induce Action...")
        cmd4 = [
            "python", "-m", "induce.induce_actions",
            "--website", args.website,
            "--result_id_list", tid,
        ]
        s4, _ = run_process_and_count(cmd4, env, task_prefix)
        print(f"{task_prefix} <<< Released Lock.")

    # --- Final Save ---
    save_task_info(tid, s1, s2, s3, s4)

def process_single_task_fast(tid, args, lock):
    """
    只执行 Step 1: Solving。
    Step 2, 3, 4 均设置为 0，但保持 JSON 格式一致。
    """
    task_prefix = f"[Task {tid}]"
    print(f"{task_prefix} Starting FAST process (Step 1 Only)...")

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    s1 = s2 = s3 = s4 = 0
    
    # --- Step 1: Solving ---
    print(f"{task_prefix} Step 1: Solving...")
    cmd1 = [
        "python", "run_demo.py",
        "--task_name", f"myBenchmark.{tid}",
        "--websites", args.website,
        "--memory_path", f"workflows/{args.website}.txt",
        "--rename_to", f"myBenchmark.{tid}",
        "--headless"
    ]
    s1, _ = run_process_and_count(cmd1, env, task_prefix)
    
    # 注意：这里不需要像完整版那样检查结果是否成功
    # 因为不需要决定是否继续 Step 2，只需记录 Step 1 消耗并保存即可
    
    # --- Final Save ---
    # s2, s3, s4 保持为 0
    save_task_info(tid, s1, s2, s3, s4)

def process_single_task_awm(tid, args, lock):
    """
    单个任务的处理逻辑。
    args: 命令行参数
    lock: 进程锁，用于保护 Step 4
    """
    task_prefix = f"[Task {tid}]"
    print(f"{task_prefix} Starting...")

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    s1 = s2 = s3 = s4 = 0
    
    # --- Step 1: Solving (并行执行) ---
    print(f"{task_prefix} Step 1: Solving...(memory)")
    cmd1 = [
        "python", "run_demo.py",
        "--task_name", f"myBenchmark.{tid}",
        "--websites", args.website,
        "--memory_path", f"workflows/{args.website}.txt",
        "--rename_to", f"myBenchmark.{tid}",
        "--headless"
    ]
    s1, _ = run_process_and_count(cmd1, env, task_prefix)
    
    # 检查 Step 1 结果
    path = f"results/myBenchmark.{tid}/summary_info.json"
    if not os.path.exists(path):
        save_task_info(tid, s1, s2, s3, s4)
        return
    try:
        if json.load(open(path, 'r')).get("n_steps", 0) < 3: 
            save_task_info(tid, s1, s2, s3, s4)
            return
    except:
        pass

    # --- Step 2: Evaluating (并行执行) ---
    print(f"{task_prefix} Step 2: Evaluating...")
    cmd2 = [
        "python", "-m", "autoeval.evaluate_trajectory",
        "--result_dir", f"results/myBenchmark.{tid}",
    ]
    s2, _ = run_process_and_count(cmd2, env, task_prefix)
    
    # 检查 Eval 结果
    path_eval = f"results/myBenchmark.{tid}/deepseek-chat_autoeval.json"
    is_correct = False
    if os.path.exists(path_eval):
        try:
            data = json.load(open(path_eval))
            if data and isinstance(data, list):
                is_correct = data[0].get("rm", False)
        except:
            pass
    
    if not is_correct: 
        save_task_info(tid, s1, s2, s3, s4)
        return

    # --- Step 3: Calculation (并行执行) ---
    print(f"{task_prefix} Step 3: Calculating...")
    cmd3 = [
        "python", "-m", "results.calc_valid_steps",
        "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
    ]
    s3, _ = run_process_and_count(cmd3, env, task_prefix)

    # --- Step 4: Inducing (串行执行 - 加锁) ---
    # 这是关键点！induce_action.py 会修改共享文件，必须加锁
    print(f"{task_prefix} Step 4: Waiting for lock to Induce Memory...")

    with lock:
        print(f"{task_prefix} >>> Acquired Lock. Running Induce Memory...")
        cmd4 = [
            "python", "-m", "induce.induce_memory",
            "--website", args.website,
            "--result_id_list", tid,
        ]
        s4, _ = run_process_and_count(cmd4, env, task_prefix)
        print(f"{task_prefix} <<< Released Lock.")

    # --- Final Save ---
    save_task_info(tid, s1, s2, s3, s4)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "admin", "reddit", "gitlab", "map", "wordpress"])
    parser.add_argument("--task_ids", type=str, required=True,
                        help="xxx-xxx,xxx-xxx")
    parser.add_argument("--workers", type=int, default=8, 
                        help="Number of parallel processes")
    # 新增参数 --fast
    parser.add_argument("--fast", action="store_true", 
                        help="If set, only runs Step 1 (Solving) and saves stats with other steps as 0.")

    args = parser.parse_args()

    task_id_list = parse_task_ids(args.task_ids)
    print(f"Total tasks to process: {len(task_id_list)}")
    if args.fast:
        print("Mode: FAST (Step 1 only)")
    else:
        print("Mode: FULL (Steps 1-4)")

    with multiprocessing.Manager() as manager:
        lock = manager.Lock()
        
        # 根据参数选择使用的函数
        target_func = process_single_task_fast if args.fast else process_single_task_awm
        
        func = partial(target_func, args=args, lock=lock)
        
        with multiprocessing.Pool(processes=args.workers) as pool:
            pool.map(func, task_id_list)

if __name__ == "__main__":
    # 设置启动方法，spawn 在某些环境下更稳定，但在 Linux 上 fork 更快
    # 如果遇到 pickling error，可以尝试取消注释下面这行
    # multiprocessing.set_start_method('spawn')
    main()