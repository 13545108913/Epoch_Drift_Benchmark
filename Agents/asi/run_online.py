import os
import json
import argparse
import subprocess
import sys
from subprocess import Popen, PIPE, STDOUT

def parse_task_ids(task_id_str: str) -> list[str]:
    chunks = [c.strip() for c in task_id_str.split(",")]
    task_id_list = []
    for c in chunks:
        s, e = [int(n.strip()) for n in c.split("-")]
        task_id_list.extend([str(i) for i in range(s, e+1)])
    return task_id_list

def count_deepseek_calls(log_output: str) -> int:
    """
    从日志文本中统计 DeepSeek API 的调用次数。
    依据日志特征: 'HTTP Request: POST https://api.deepseek.com/chat/completions'
    """
    if not log_output:
        return 0
    keyword = "HTTP Request: POST https://api.deepseek.com/chat/completions"
    return log_output.count(keyword)

def save_task_info(task_id, step1, step2, step3, step4):
    """保存统计结果到 JSON 文件"""
    total = step1 + step2 + step3 + step4
    # 格式化输出字符串
    info_str = f"Task [{task_id}]: Total {total} (step1_solve: {step1}, step2_eval: {step2}, step3_cal: {step3}, step4_induce: {step4})"
    
    os.makedirs("./llm_info", exist_ok=True)
    save_path = f"./llm_info/{task_id}.json"
    
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump({"result": info_str}, f, ensure_ascii=False, indent=2)
    
    # 打印显眼的提示
    print(f"\n>>> [STATS SAVED] {info_str}\n")

def run_process_and_count(cmd, env=None):
    """
    运行子进程，支持实时打印输出（流式），并在结束后返回 API 调用统计。
    """
    print(f"Executing: {' '.join(cmd)}")
    
    # stderr=STDOUT 表示将错误流合并到标准输出流，方便统一抓取和打印
    process = Popen(cmd, stdout=PIPE, stderr=STDOUT, env=env, text=True, encoding='utf-8', errors='replace')
    
    full_log = []
    
    try:
        # 实时逐行读取输出
        for line in process.stdout:
            print(line, end='') # 实时打印到屏幕，保持用户可见性
            full_log.append(line) # 存入内存用于后续统计
            
        process.wait() # 等待进程彻底退出
    except KeyboardInterrupt:
        # 允许用户按 Ctrl+C 强行终止子进程
        print("\nStopping process...")
        process.kill()
        process.wait()
        raise
        
    # 合并所有日志进行统计
    full_log_str = "".join(full_log)
    count = count_deepseek_calls(full_log_str)
    
    return count, full_log_str

# %% ASI
def run_asi():
    task_id_list = parse_task_ids(args.task_ids)
    
    # === 关键修改 ===
    # 设置环境变量，强制 Python 不缓存输出
    # 这样孙子进程的日志也能由管道顺畅地传导上来
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    for tid in task_id_list:
        print(f"================ Processing Task {tid} ================")
        
        # 初始化各阶段计数
        s1 = s2 = s3 = s4 = 0
        
        # --- Step 1: Solving ---
        print(f"[{tid}] Step 1: Solving...")
        cmd1 = [
            "python", "run_demo.py",
            "--task_name", f"myBenchmark.{tid}",
            "--websites", args.website,
            "--rename_to", f"myBenchmark.{tid}",
            "--headless"
        ]
        s1, _ = run_process_and_count(cmd1, env)
        
        # 检查是否由于 Step 1 失败需要提前结束
        path = f"results/myBenchmark.{tid}/summary_info.json"
        
        # 情况A: 文件不存在 -> 失败
        if not os.path.exists(path):
            save_task_info(tid, s1, s2, s3, s4)
            continue
            
        # 情况B: 步数过少 -> 失败
        try:
            if json.load(open(path, 'r')).get("n_steps", 0) < 3: 
                save_task_info(tid, s1, s2, s3, s4)
                continue
        except:
            pass

        # --- Step 2: Evaluating ---
        print(f"[{tid}] Step 2: Evaluating...")
        cmd2 = [
            "python", "-m", "autoeval.evaluate_trajectory",
            "--result_dir", f"results/myBenchmark.{tid}",
        ]
        s2, _ = run_process_and_count(cmd2, env)
        
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
            continue

        # --- Step 3: Calculation (原 Step 2.2) ---
        print(f"[{tid}] Step 3: Calculating Valid Steps...")
        cmd3 = [
            "python", "-m", "results.calc_valid_steps",
            "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
        ]
        s3, _ = run_process_and_count(cmd3, env)

        # --- Step 4: Inducing (原 Step 3) ---
        print(f"[{tid}] Step 4: Inducing Actions...")
        cmd4 = [
            "python", "-m", "induce.induce_actions",
            "--website", args.website,
            "--result_id_list", tid,
        ]
        s4, _ = run_process_and_count(cmd4, env)

        # --- Final Save ---
        save_task_info(tid, s1, s2, s3, s4)

def run_awm():
    task_id_list = parse_task_ids(args.task_ids)
    
    # === 关键修改 ===
    # 设置环境变量，强制 Python 不缓存输出
    # 这样孙子进程的日志也能由管道顺畅地传导上来
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    for tid in task_id_list:
        print(f"================ Processing Task {tid} ================")
        
        # 初始化各阶段计数
        s1 = s2 = s3 = s4 = 0
        
        # --- Step 1: Solving ---
        print(f"[{tid}] Step 1: Solving...")
        cmd1 = [
            "python", "run_demo.py",
            "--task_name", f"myBenchmark.{tid}",
            "--websites", args.website,
            "--memory_path", f"workflows/{args.website}.txt",
            "--rename_to", f"myBenchmark.{tid}",
            "--headless"
        ]
        s1, _ = run_process_and_count(cmd1, env)
        
        # 检查是否由于 Step 1 失败需要提前结束
        path = f"results/myBenchmark.{tid}/summary_info.json"
        
        # 情况A: 文件不存在 -> 失败
        if not os.path.exists(path):
            save_task_info(tid, s1, s2, s3, s4)
            continue
            
        # 情况B: 步数过少 -> 失败
        try:
            if json.load(open(path, 'r')).get("n_steps", 0) < 3: 
                save_task_info(tid, s1, s2, s3, s4)
                continue
        except:
            pass

        # --- Step 2: Evaluating ---
        print(f"[{tid}] Step 2: Evaluating...")
        cmd2 = [
            "python", "-m", "autoeval.evaluate_trajectory",
            "--result_dir", f"results/myBenchmark.{tid}",
        ]
        s2, _ = run_process_and_count(cmd2, env)
        
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
            continue

        # --- Step 3: Calculation (原 Step 2.2) ---
        print(f"[{tid}] Step 3: Calculating Valid Steps...")
        cmd3 = [
            "python", "-m", "results.calc_valid_steps",
            "--clean_and_store", "--result_dir", f"results/myBenchmark.{tid}",
        ]
        s3, _ = run_process_and_count(cmd3, env)

        # --- Step 4: Inducing (原 Step 3) ---
        print(f"[{tid}] Step 4: Inducing Actions...")
        cmd4 = [
            "python", "-m", "induce.induce_memory",
            "--website", args.website,
            "--result_id_list", tid,
        ]
        s4, _ = run_process_and_count(cmd4, env)

        # --- Final Save ---
        save_task_info(tid, s1, s2, s3, s4)

# %% Main Pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=str, required=True,
                        choices=["shopping", "admin", "reddit", "gitlab", "map"])
    parser.add_argument("--task_ids", type=str, required=True,
                        help="xxx-xxx,xxx-xxx")

    args = parser.parse_args()

    run_awm()