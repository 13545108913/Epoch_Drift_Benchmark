import os
import json
import re

# ================= 配置区域 =================
# 假设脚本运行在 Agents/SkillWeaver/ 目录下，或者你可以改为绝对路径
DIR_V12 = "results/gitlab_with_skills/gitlab"
DIR_V16 = "results/gitlab_with_skills_v16/gitlab"

OUTPUT_FILE = "version_comparison_report.txt"
# ===========================================

def get_task_id_number(task_folder_name):
    """从 task_123 中提取数字 123 用于排序"""
    match = re.search(r'task_(\d+)', task_folder_name)
    return int(match.group(1)) if match else -1

def load_task_data(base_dir, task_folder):
    """
    读取指定目录下的任务数据
    返回: {
        "success": bool,
        "score": float,
        "task_desc": str,
        "reason": str
    }
    """
    task_path = os.path.join(base_dir, task_folder)
    task_json_path = os.path.join(task_path, "task.json")
    eval_json_path = os.path.join(task_path, "eval.json")
    
    result = {
        "success": False,
        "score": 0.0,
        "task_desc": "Unknown Task",
        "reason": "Data missing or file not found"
    }

    # 1. 读取任务描述
    if os.path.exists(task_json_path):
        try:
            with open(task_json_path, 'r', encoding='utf-8') as f:
                tj = json.load(f)
                result["task_desc"] = tj.get("task", "Unknown Task")
        except Exception:
            pass

    # 2. 读取评估结果
    if os.path.exists(eval_json_path):
        try:
            with open(eval_json_path, 'r', encoding='utf-8') as f:
                ej = json.load(f)
                score = ej.get("score", 0.0)
                result["score"] = score
                result["success"] = (score == 1.0)
                
                # 提取原因
                checks = ej.get("checks", [])
                if checks and len(checks) > 0:
                    # 优先取第一个 check 的 reason
                    result["reason"] = checks[0].get("reason", "No reason provided")
                else:
                    result["reason"] = "No checks recorded"
        except Exception as e:
            result["reason"] = f"Error reading eval.json: {str(e)}"
    else:
        result["reason"] = "eval.json not found (Task likely crashed)"

    return result

def main():
    print("Starting comparison analysis...")
    
    # 获取所有 task_x 文件夹
    tasks_v12 = {d for d in os.listdir(DIR_V12) if d.startswith("task_") and os.path.isdir(os.path.join(DIR_V12, d))} if os.path.exists(DIR_V12) else set()
    tasks_v16 = {d for d in os.listdir(DIR_V16) if d.startswith("task_") and os.path.isdir(os.path.join(DIR_V16, d))} if os.path.exists(DIR_V16) else set()
    
    # 取并集，确保两个版本中存在的任务都被统计
    all_tasks = sorted(list(tasks_v12 | tasks_v16), key=get_task_id_number)
    
    categories = {
        "v12_success_v16_fail": [], # Regression
        "v16_success_v12_fail": [], # Improvement
        "both_success": [],
        "both_fail": []
    }

    count = 0
    for task_id in all_tasks:
        data_v12 = load_task_data(DIR_V12, task_id)
        data_v16 = load_task_data(DIR_V16, task_id)
        
        # 统一任务描述（优先用v16的，如果没有则用v12的）
        task_desc = data_v16["task_desc"] if data_v16["task_desc"] != "Unknown Task" else data_v12["task_desc"]
        
        item = {
            "id": task_id,
            "desc": task_desc,
            "v12_reason": data_v12["reason"],
            "v16_reason": data_v16["reason"]
        }

        if data_v12["success"] and not data_v16["success"]:
            categories["v12_success_v16_fail"].append(item)
        elif not data_v12["success"] and data_v16["success"]:
            categories["v16_success_v12_fail"].append(item)
        elif data_v12["success"] and data_v16["success"]:
            categories["both_success"].append(item)
        else:
            categories["both_fail"].append(item)
            
        count += 1

    # ================= 生成报告 =================
    lines = []
    lines.append("COMPARISON REPORT: v12 vs v16")
    lines.append("=" * 60)
    lines.append(f"Total Tasks Analyzed: {count}")
    lines.append(f"Regression (v12 OK -> v16 Fail) : {len(categories['v12_success_v16_fail'])}")
    lines.append(f"Improvement (v12 Fail -> v16 OK): {len(categories['v16_success_v12_fail'])}")
    lines.append(f"Both Success                    : {len(categories['both_success'])}")
    lines.append(f"Both Fail                       : {len(categories['both_fail'])}")
    lines.append("\n")

    def write_section(title, task_list, include_reasons=True):
        lines.append(f"[{title}] - Count: {len(task_list)}")
        lines.append("-" * 60)
        if not task_list:
            lines.append("None")
        for t in task_list:
            lines.append(f"Task: {t['id']}")
            lines.append(f"Content: {t['desc']}")
            if include_reasons:
                lines.append(f"  v12 Result: {t['v12_reason']}")
                lines.append(f"  v16 Result: {t['v16_reason']}")
            lines.append("") # Empty line
        lines.append("\n")

    # 1. 倒退的任务 (重点关注)
    write_section("REGRESSION (v12 Success, v16 Fail)", categories["v12_success_v16_fail"])

    # 2. 改进的任务
    write_section("IMPROVEMENT (v12 Fail, v16 Success)", categories["v16_success_v12_fail"])

    # 3. 都失败的任务 (可能是硬骨头)
    write_section("BOTH FAILED", categories["both_fail"])

    # 4. 都成功的任务 (可以简略显示，不打印太长的Reason)
    lines.append(f"[BOTH SUCCESS] - Count: {len(categories['both_success'])}")
    lines.append("-" * 60)
    # 提取ID列表即可，节省篇幅
    success_ids = [t['id'] for t in categories['both_success']]
    lines.append(", ".join(success_ids))
    lines.append("\n")

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        print(f"Report saved to: {os.path.abspath(OUTPUT_FILE)}")
    except Exception as e:
        print(f"Error saving report: {e}")

if __name__ == "__main__":
    main()