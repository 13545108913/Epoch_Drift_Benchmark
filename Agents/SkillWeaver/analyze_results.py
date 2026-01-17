import ast
import os
import json
import glob
import re
from collections import defaultdict

# ================= 配置区域 =================
# 结果所在的根目录
BASE_DIR = "results_admin/admin_with_skills_v2_waber/shopping_admin"

# 代码知识库路径
KB_PATH = os.path.join(BASE_DIR, "kb_code.py")

# 任务总数 (0 ~ 161)
TASK_COUNT = 162

# 单个任务分析文件的名称
TASK_OUTPUT_FILENAME = "task_analysis.txt"

# 全局汇总文件的名称
GLOBAL_OUTPUT_FILENAME = "global_analysis_summary.txt"
# ===========================================

def load_kb_code(kb_path):
    if not os.path.exists(kb_path):
        return []
    with open(kb_path, 'r', encoding='utf-8') as f:
        return f.readlines()

def get_function_names(file_path):
    if not os.path.exists(file_path):
        print(f"错误: 找不到文件 {file_path}")
        return []
    with open(file_path, "r", encoding="utf-8") as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError as e:
            print(f"解析错误 {file_path}: {e}")
            return []

    function_names = []
    # 遍历语法树中的所有节点
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_names.append(node.name)
    return function_names

def get_token_stats(task_dir):
    stats = {
        "llm_call_count": 0,
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0
    }
    perf_path = os.path.join(task_dir, "perfmon.json")
    if os.path.exists(perf_path):
        try:
            with open(perf_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                usages = data.get("token_usages", [])
                stats["llm_call_count"] = len(usages)
                for u in usages:
                    i_tok = u.get("input_tokens", 0)
                    o_tok = u.get("output_tokens", 0)
                    stats["input_tokens"] += i_tok
                    stats["output_tokens"] += o_tok
                    stats["total_tokens"] += (i_tok + o_tok)
        except Exception:
            pass
    return stats

def get_task_score(task_dir):
    """
    获取任务得分 (从 eval.json 中读取 score)
    """
    eval_path = os.path.join(task_dir, "eval.json")
    if os.path.exists(eval_path):
        try:
            with open(eval_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 获取分数，如果存在的话
                if "score" in data:
                    return float(data["score"])
        except Exception:
            pass
    return None

def find_line_number(content_lines, target_line_str):
    target_clean = target_line_str.strip()
    if not target_clean:
        return -1
    for i, line in enumerate(content_lines):
        if target_clean in line:
            return i + 1
    return -1

def analyze_error(action_file_data, kb_lines):
    """
    分析单个 Action 文件中的错误
    """
    data = action_file_data # 传入已读取的json data
    if not data.get("result") or not isinstance(data["result"], dict) or not data["result"].get("exception"):
        return None
    
    exception_info = data["result"]["exception"]
    error_type = exception_info.get("type", "UnknownError")
    error_msg = str(exception_info.get("args", [""]))
    tb_str = exception_info.get("traceback", "")
    formatted_code = data.get("formatted_code", "")

    frames = re.findall(r'File "(.+?)", line (\d+), in (.+?)\n\s+(.+)', tb_str)
    
    relevant_frame = None
    for filepath, lineno, func_name, code_content in reversed(frames):
        if "site-packages" not in filepath and "dist-packages" not in filepath and BASE_DIR in filepath:
            relevant_frame = (func_name, code_content.strip())
            break
    
    if not relevant_frame:
        return {
            "source": "Library/Unknown",
            "line_no": "N/A",
            "code_content": "N/A",
            "error_msg": f"{error_type}: {error_msg}"
        }

    func_name, code_content = relevant_frame

    # 1. Check Knowledge Base
    kb_line_no = find_line_number(kb_lines, code_content)
    if kb_line_no != -1 and func_name != "act":
        return {
            "source": "Knowledge Base (kb_code.py)",
            "line_no": kb_line_no,
            "code_content": code_content,
            "function_name": func_name,
            "error_msg": f"{error_type}: {error_msg}"
        }

    # 2. Check Formatted Code
    fmt_lines = formatted_code.split('\n')
    fmt_line_no = find_line_number(fmt_lines, code_content)
    if fmt_line_no != -1:
        return {
            "source": "Formatted Code (Generated)",
            "line_no": fmt_line_no,
            "code_content": code_content,
            "function_name": func_name,
            "error_msg": f"{error_type}: {error_msg}"
        }

    return {
        "source": "Unknown/Check Manually",
        "line_no": "Unknown",
        "code_content": code_content,
        "function_name": func_name,
        "error_msg": f"{error_type}: {error_msg}"
    }

def count_kb_usage(action_files, kb_func_names):
    """
    统计该任务中所有 KB 函数的调用次数
    """
    usage_stats = defaultdict(int)
    if not kb_func_names:
        return usage_stats
    
    # 预编译正则以提高效率: 匹配单词边界，防止 calculate 匹配到 calculate_sum
    patterns = {func: re.compile(rf'\b{func}\b') for func in kb_func_names}

    for af in action_files:
        try:
            with open(af, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 代码通常在 formatted_code 中
                code = data.get("formatted_code", "")
                if not code: 
                    continue
                
                # 统计每个函数在代码块中的出现次数
                for func, pattern in patterns.items():
                    # findAll 返回所有匹配列表，len 即为次数
                    matches = pattern.findall(code)
                    if matches:
                        usage_stats[func] += len(matches)
        except Exception:
            continue
            
    return usage_stats

def process_single_task(task_index, kb_lines, kb_func_names):
    """
    处理单个任务：
    1. 生成该任务的独立分析文件
    2. 返回该任务的统计信息、错误列表、KB函数调用统计、得分以及是否发生运行时错误
    """
    task_name = f"task_{task_index}"
    task_dir = os.path.join(BASE_DIR, task_name)
    
    # 如果文件夹不存在，跳过
    if not os.path.exists(task_dir):
        return None, [], {}, None, False

    # [新增] 判断是否是 Runtime Error (eval.json 不存在)
    eval_path = os.path.join(task_dir, "eval.json")
    is_runtime_error = not os.path.exists(eval_path)

    # 1. 获取Token统计
    token_stats = get_token_stats(task_dir)
    
    # 2. 获取任务得分
    task_score = get_task_score(task_dir)

    # 3. 获取所有 Action 文件
    action_files = sorted(glob.glob(os.path.join(task_dir, "*_action.json")))
    
    # 4. 分析报错 (即使是 Runtime Error，也可能前面几步有报错信息，值得分析)
    errors = []
    for af in action_files:
        step_name = os.path.basename(af).split('_')[0]
        try:
            with open(af, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            continue
            
        error_info = analyze_error(data, kb_lines)
        if error_info:
            error_info['step'] = step_name
            error_info['task'] = task_name 
            errors.append(error_info)

    # 5. 统计 KB 函数使用情况
    kb_usage = count_kb_usage(action_files, kb_func_names)

    # 6. 写入单任务报告
    report_lines = []
    report_lines.append(f"Analysis Report for {task_name}")
    report_lines.append("=" * 50)
    
    # 写入状态判断
    if is_runtime_error:
        status_str = "RUNTIME ERROR (Missing eval.json)"
    elif task_score is not None and task_score > 0:
        status_str = "SUCCESS"
    else:
        status_str = "FAILURE"
    
    report_lines.append(f"[0] Task Status: {status_str}")
    score_display = task_score if task_score is not None else "N/A"
    report_lines.append(f"    Task Score: {score_display}")

    report_lines.append("\n[1] LLM Token Statistics")
    report_lines.append(f"Calls: {token_stats['llm_call_count']}, Total Tokens: {token_stats['total_tokens']}")
    
    report_lines.append("\n[2] KB Function Usage (Local)")
    if not kb_usage:
        report_lines.append("No KB functions called.")
    else:
        # 按调用次数倒序排列
        for func, count in sorted(kb_usage.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"  - {func}: {count}")
            
    report_lines.append("\n[3] Execution Errors")
    if not errors:
        report_lines.append("No python exceptions found in action files.")
    else:
        for idx, err in enumerate(errors, 1):
            report_lines.append(f"Error #{idx} (Step: {err['step']}) - Source: {err['source']}")
            report_lines.append(f"  Line {err['line_no']} in {err.get('function_name', 'N/A')}: {err['code_content']}")
            report_lines.append(f"  {err['error_msg']}\n")

    output_path = os.path.join(task_dir, TASK_OUTPUT_FILENAME)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))
    except Exception:
        pass

    return token_stats, errors, kb_usage, task_score, is_runtime_error

def main():
    print(f"Starting analysis for {TASK_COUNT} tasks...")
    
    kb_lines = load_kb_code(KB_PATH)
    # 提取 KB 中的函数列表
    kb_func_names = get_function_names(KB_PATH)
    print(f"Loaded {len(kb_func_names)} functions from Knowledge Base. {kb_func_names}")

    # 全局累加器
    global_stats = {
        "processed_tasks": 0,
        "total_calls": 0,
        "total_tokens": 0
    }
    
    # 分数统计累加器
    global_score_stats = {
        "total_score": 0.0,
        "scored_tasks_count": 0
    }

    # 全局 KB 函数调用计数
    global_kb_usage = defaultdict(int)
    
    # 专门收集 Knowledge Base 的错误
    all_kb_errors = []

    # [新增] 收集发生 Runtime Error 的任务
    runtime_error_tasks = []

    for i in range(TASK_COUNT):
        # 处理单个任务
        stats, errors, kb_usage, score, is_rt_error = process_single_task(i, kb_lines, kb_func_names)
        
        if stats is not None:
            global_stats["processed_tasks"] += 1
            global_stats["total_calls"] += stats["llm_call_count"]
            global_stats["total_tokens"] += stats["total_tokens"]
            
            # 统计分数
            if score is not None:
                global_score_stats["total_score"] += score
                global_score_stats["scored_tasks_count"] += 1
            
            # 统计 Runtime Error
            if is_rt_error:
                runtime_error_tasks.append(f"task_{i}")

            # 累加 KB 函数调用
            for func, count in kb_usage.items():
                global_kb_usage[func] += count
            
            # 筛选 KB 错误
            for err in errors:
                if "Knowledge Base" in err["source"]:
                    all_kb_errors.append(err)

    # ================= 生成全局汇总报告 =================
    summary_lines = []
    summary_lines.append("GLOBAL ANALYSIS SUMMARY")
    summary_lines.append("=" * 60)
    
    num_tasks = global_stats["processed_tasks"]
    if num_tasks == 0:
        print("No tasks were processed. Check your paths.")
        return

    # 1. 基础统计
    avg_calls = global_stats["total_calls"] / num_tasks
    avg_tokens = global_stats["total_tokens"] / num_tasks
    
    summary_lines.append(f"Total Tasks Found     : {num_tasks}")
    summary_lines.append("-" * 30)

    # 1.1 分数统计
    scored_count = global_score_stats["scored_tasks_count"]
    total_score = global_score_stats["total_score"]
    avg_score = total_score / scored_count if scored_count > 0 else 0.0

    summary_lines.append("EVALUATION SCORE STATISTICS")
    summary_lines.append(f"Tasks with Scores     : {scored_count}")
    summary_lines.append(f"Total Score Sum       : {total_score:.2f}")
    summary_lines.append(f"Average Score         : {avg_score:.4f}")
    
    # [新增] Runtime Error 统计
    summary_lines.append("-" * 30)
    summary_lines.append("RUNTIME ERROR STATISTICS")
    summary_lines.append(f"Total Runtime Errors  : {len(runtime_error_tasks)}")
    if runtime_error_tasks:
        summary_lines.append(f"Tasks List            : {', '.join(runtime_error_tasks)}")
    else:
        summary_lines.append("Tasks List            : None")
    
    summary_lines.append("-" * 30)
    summary_lines.append(f"Average LLM Calls     : {avg_calls:.2f}")
    summary_lines.append(f"Average Tokens Used   : {avg_tokens:.2f}")
    summary_lines.append("\n")

    # 2. KB 函数调用统计
    summary_lines.append("KB FUNCTION USAGE STATISTICS (Average calls per task)")
    summary_lines.append("-" * 60)
    summary_lines.append(f"{'Function Name':<40} | {'Total Calls':<12} | {'Avg/Task':<10}")
    summary_lines.append("-" * 66)
    
    # 对函数按平均调用次数倒序排序
    sorted_usage = sorted(global_kb_usage.items(), key=lambda x: x[1], reverse=True)
    
    tmp = 0
    for func, total in sorted_usage:
        tmp += total
        avg_usage = total / num_tasks
        summary_lines.append(f"{func:<40} | {total:<12} | {avg_usage:<10.2f}")
    summary_lines.append(f"total | {tmp:<12} | {(tmp/num_tasks):<10.3f}")

    if not sorted_usage:
        summary_lines.append("No KB functions were called across all tasks.")
    summary_lines.append("\n")

    # 3. Knowledge Base 错误汇总
    summary_lines.append(f"KNOWLEDGE BASE ERRORS FOUND: {len(all_kb_errors)}")
    summary_lines.append("=" * 60)
    if not all_kb_errors:
        summary_lines.append("No errors originated from the Knowledge Base code.")
    else:
        all_kb_errors.sort(key=lambda x: x.get('function_name', ''))
        
    for idx, err in enumerate(all_kb_errors, 1):
        summary_lines.append(f"[{idx}] Task: {err['task']} | Step: {err['step']}")
        summary_lines.append(f"    Function : {err.get('function_name', 'Unknown')}")
        summary_lines.append(f"    Line No  : {err['line_no']}")
        summary_lines.append(f"    Code     : {err['code_content']}")
        summary_lines.append(f"    Error    : {err['error_msg']}")
        summary_lines.append("-" * 40)

    # 写入全局汇总文件
    summary_path = os.path.join(BASE_DIR, GLOBAL_OUTPUT_FILENAME)
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(summary_lines))
        print(f"\nGlobal summary saved to: {summary_path}")
        print(f"Runtime Errors Found: {len(runtime_error_tasks)}")
        print(f"Average Score: {avg_score:.4f}")
        print(f"Individual task reports saved in each task folder.")
    except Exception as e:
        print(f"Failed to save global summary: {e}")

if __name__ == "__main__":
    main()
