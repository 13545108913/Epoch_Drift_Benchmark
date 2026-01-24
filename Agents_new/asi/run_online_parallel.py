import os
import json
import argparse
import subprocess
import sys
from subprocess import Popen, PIPE, STDOUT
import multiprocessing
from functools import partial

# --- 辅助函数 ---

def parse_task_ids(task_id_str: str) -> list[str]:
    chunks = [c.strip() for c in task_id_str.split(",")]
    task_id_list = []
    for c in chunks:
        s, e = [int(n.strip()) for n in c.split("-")]
        task_id_list.extend([str(i) for i in range(s, e+1)])
    return task_id_list

def run_process(cmd, env=None, task_prefix=""):
    """
    运行子进程。不再统计调用次数，不再缓存所有日志。
    """
    # 如果想在终端看到实时输出，可以取消下面这一行的注释
    # print(f"{task_prefix} Executing: {' '.join(cmd)}") 
    
    # 使用 Popen 运行
    process = Popen(cmd, stdout=PIPE, stderr=STDOUT, env=env, text=True, encoding='utf-8', errors='replace')
    
    try:
        # 实时读取输出，防止缓冲区填满导致挂起，但不保存用于统计
        for line in process.stdout:
            # 如果需要调试可以看到输出，否则静默运行以保持清爽
            # print(f"{task_prefix} {line}", end='') 
            pass
            
        process.wait()
    except KeyboardInterrupt:
        print(f"\n{task_prefix} Stopping process...")
        process.kill()
        process.wait()
        raise
        
    return

# --- 核心逻辑重构 ---

def process_single_task(tid, args, lock):
    """
    单个任务的处理逻辑 (完整流程: Step 1->2->3->4)
    """
    task_prefix = f"[Task {tid}]"
    print(f"{task_prefix} Starting...")

    # 设置环境变量
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    # --- Step 1: Solving (并行执行) ---
    print(f"{task_prefix} Step 1: Solving(ASI)...")
    cmd1 = [
        "python", "run_demo.py",
        "--task_name", f"myBenchmark.{tid}",
        "--websites", args.website,
        "--rename_to", f"myBenchmark.{tid}",
        "--headless"
    ]
    run_process(cmd1, env, task_prefix)
    
    # 检查 Step 1 结果 (决定是否继续)
    path = f"results/myBenchmark.{tid}/summary_info.json"
    if not os.path.exists(path):
        print(f"{task_prefix} Step 1 failed (no summary), skipping rest.")
        return
    try:
        if json.load(open(path, 'r')).get("n_steps", 0) < 3: 
            print(f"{task_prefix} Step 1 failed (steps < 3), skipping rest.")
            return
    except:
        pass

    # --- Step 2: Evaluating (并行执行) ---
    print(f"{task_prefix} Step 2: Evaluating...")
    cmd2 = [
        "python", "-m", "autoeval.evaluate_trajectory",
        "--result_dir", f"results/myBenchmark.{tid}",
    ]
    run_process(cmd2, env, task_prefix)
    
    # 检查 Eval 结果 (决定是否继续)
    path_eval = f"results/myBenchmark.{tid}/autoeval.json"
    is_correct = False
    if os.path.exists(path_eval):
        try:
            data = json.load(open(path_eval))
            if data and isinstance(data, list):
                is_correct = data[0].get("rm", False)
        except:
            pass
    
    if not is_correct: 
        print(f"{task_prefix} Evaluation failed, skipping calculation/inducing.")
        return

    # --- Step 3: Calculation (并行执行) ---
    print(f"{task_prefix} Step 3: Calculating...")
    cmd3 = [
        "python", "-m", "results.calc_valid_steps",
        "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
    ]
    run_process(cmd3, env, task_prefix)

    # --- Step 4: Inducing (串行执行 - 加锁) ---
    print(f"{task_prefix} Step 4: Waiting for lock to Induce Actions...")
    
    with lock:
        print(f"{task_prefix} >>> Acquired Lock. Running Induce Action...")
        cmd4 = [
            "python", "-m", "induce.induce_actions",
            "--website", args.website,
            "--result_id_list", tid,
        ]
        run_process(cmd4, env, task_prefix)
        print(f"{task_prefix} <<< Released Lock.")

    print(f"{task_prefix} Done.")

def process_single_task_fast(tid, args, lock):
    """
    快速模式：只执行 Step 1: Solving。
    """
    task_prefix = f"[Task {tid}]"
    print(f"{task_prefix} Starting FAST process (Step 1 Only)...")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
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
    run_process(cmd1, env, task_prefix)
    print(f"{task_prefix} Done.")

def process_single_task_awm(tid, args, lock):
    """
    AWM 模式处理逻辑
    """
    task_prefix = f"[Task {tid}]"
    print(f"{task_prefix} Starting...")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    # --- Step 1: Solving (memory) ---
    print(f"{task_prefix} Step 1: Solving...(memory)")
    cmd1 = [
        "python", "run_demo.py",
        "--task_name", f"myBenchmark.{tid}",
        "--websites", args.website,
        "--memory_path", f"workflows/{args.website}.txt",
        "--rename_to", f"myBenchmark.{tid}",
        "--headless"
    ]
    run_process(cmd1, env, task_prefix)
    
    path = f"results/myBenchmark.{tid}/summary_info.json"
    if not os.path.exists(path):
        return
    try:
        if json.load(open(path, 'r')).get("n_steps", 0) < 3: 
            return
    except:
        pass

    # --- Step 2: Evaluating ---
    print(f"{task_prefix} Step 2: Evaluating...")
    cmd2 = [
        "python", "-m", "autoeval.evaluate_trajectory",
        "--result_dir", f"results/myBenchmark.{tid}",
    ]
    run_process(cmd2, env, task_prefix)
    
    path_eval = f"results/myBenchmark.{tid}/autoeval.json"
    is_correct = False
    if os.path.exists(path_eval):
        try:
            data = json.load(open(path_eval))
            if data and isinstance(data, list):
                is_correct = data[0].get("rm", False)
        except:
            pass
    
    if not is_correct: 
        return

    # --- Step 3: Calculation ---
    print(f"{task_prefix} Step 3: Calculating...")
    cmd3 = [
        "python", "-m", "results.calc_valid_steps",
        "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
    ]
    run_process(cmd3, env, task_prefix)

    # --- Step 4: Inducing ---
    print(f"{task_prefix} Step 4: Waiting for lock to Induce Memory...")

    with lock:
        print(f"{task_prefix} >>> Acquired Lock. Running Induce Memory...")
        cmd4 = [
            "python", "-m", "induce.induce_memory",
            "--website", args.website,
            "--result_id_list", tid,
        ]
        run_process(cmd4, env, task_prefix)
        print(f"{task_prefix} <<< Released Lock.")
        
    print(f"{task_prefix} Done.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "admin", "reddit", "gitlab", "map", "wordpress"])
    parser.add_argument("--task_ids", type=str, required=True,
                        help="xxx-xxx,xxx-xxx")
    parser.add_argument("--workers", type=int, default=8, 
                        help="Number of parallel processes")
    parser.add_argument("--fast", action="store_true", 
                        help="If set, only runs Step 1 (Solving).")
    # 如果还需要 awm 模式的开关，可以在这里添加，或者根据已有逻辑调用
    # parser.add_argument("--awm", action="store_true", help="Run AWM mode")

    args = parser.parse_args()

    task_id_list = parse_task_ids(args.task_ids)
    print(f"Total tasks to process: {len(task_id_list)}")
    
    if args.fast:
        print("Mode: FAST (Step 1 only)")
        target_func = process_single_task_fast
    else:
        # 如果你有 --awm 参数需求，可以在这里加判断切换到 process_single_task_awm
        print("Mode: FULL (Steps 1-4)")
        target_func = process_single_task_awm

    # M1 芯片使用 spawn 方式通常更稳定，但 Python 3.8+ 在 macOS 默认已经是 spawn
    # 如果遇到 pickling 错误，可以显式开启下面这行：
    multiprocessing.set_start_method('spawn', force=True)

    with multiprocessing.Manager() as manager:
        lock = manager.Lock()
        
        func = partial(target_func, args=args, lock=lock)
        
        with multiprocessing.Pool(processes=args.workers) as pool:
            pool.map(func, task_id_list)

if __name__ == "__main__":
    main()