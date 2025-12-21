import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any

def analyze_webarena_results(result_dir: str = "./results", llm_info_dir: str = "./llm_info") -> Dict:
    """
    分析WebArena任务运行结果，包含LLM调用统计
    
    Args:
        result_dir: 结果目录路径
        llm_info_dir: LLM信息目录路径
        
    Returns:
        包含统计信息的字典
    """
    result_path = Path(result_dir)
    llm_info_path = Path(llm_info_dir)
    
    if not result_path.exists():
        raise FileNotFoundError(f"结果目录 {result_dir} 不存在")
    
    # 初始化统计变量
    total_tasks = 0
    successful_tasks = 0
    
    # 步骤统计列表
    all_steps = []
    successful_steps = []
    failed_steps = []
    
    # 分数统计列表
    all_scores = []
    successful_scores = []
    failed_scores = []
    
    # LLM调用统计列表 (存储字典)
    # 结构: {"total": int, "step1": int, "step2": int, "step3": int, "step4": int}
    all_llm_usage = []
    successful_llm_usage = []
    failed_llm_usage = []
    
    # 错误信息统计
    error_messages = []
    tasks_with_errors = 0
    tasks_without_errors = 0
    
    # 遍历结果目录
    for task_dir in result_path.iterdir():
        if task_dir.is_dir() and task_dir.name.startswith("myBenchmark.") and not task_dir.name.endswith("test"):
            task_id = task_dir.name.split(".")[1]
                
            total_tasks += 1
            
            # 文件路径
            autoeval_file = task_dir / "deepseek-chat_autoeval.json"
            cleaned_steps_file = task_dir / "cleaned_steps.json" # 用于 step3 统计
            summary_file = task_dir / "summary_info.json"
            llm_file = llm_info_path / f"{task_id}.json" # LLM info 文件
            
            # 1. 获取步骤数、分数和错误信息
            n_steps = None
            score = None
            err_msg = None
            
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        n_steps = summary_data.get("n_steps")
                        if n_steps is not None:
                            all_steps.append(n_steps)
                            
                        raw_score = summary_data.get("cum_reward")
                        if raw_score is not None:
                            try:
                                score = float(raw_score)
                                all_scores.append(score)
                            except (ValueError, TypeError):
                                score = None

                        err_msg = summary_data.get("err_msg")
                        if err_msg is not None:
                            tasks_with_errors += 1
                            error_messages.append({"task_id": task_id, "err_msg": err_msg})
                        else:
                            tasks_without_errors += 1
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # 2. 获取 LLM 调用信息并应用逻辑
            llm_data = None
            if llm_file.exists():
                try:
                    with open(llm_file, 'r', encoding='utf-8') as f:
                        llm_json = json.load(f)
                        result_str = llm_json.get("result", "")
                        # 解析字符串: "Task [0]: Total 2 (step1_solve: 2, step2_eval: 0, step3_cal: 0, step4_induce: 0)"
                        # 使用正则提取
                        match = re.search(r"step1_solve:\s*(\d+).*?step2_eval:\s*(\d+).*?step3_cal:\s*(\d+).*?step4_induce:\s*(\d+)", result_str)
                        
                        if match:
                            s1 = int(match.group(1))
                            s2 = int(match.group(2))
                            s3 = int(match.group(3))
                            s4 = int(match.group(4))
                            
                            # --- 应用自定义统计逻辑 ---
                            # 如果存在 deepseek-chat_autoeval.json，则 step2_eval + 1
                            if autoeval_file.exists():
                                s2 += 1
                            
                            # 如果存在 cleaned_steps.json，则 step3_cal + 1
                            if cleaned_steps_file.exists():
                                s3 += 1
                            
                            # 重新计算 Total
                            total_calls = s1 + s2 + s3 + s4
                            
                            llm_data = {
                                "total": total_calls,
                                "step1_solve": s1,
                                "step2_eval": s2,
                                "step3_cal": s3,
                                "step4_induce": s4
                            }
                            all_llm_usage.append(llm_data)
                except Exception as e:
                    print(f"警告: 读取LLM文件 {llm_file} 失败: {e}")

            # 3. 检查任务是否成功并分类数据
            task_success = False
            if autoeval_file.exists():
                try:
                    with open(autoeval_file, 'r', encoding='utf-8') as f:
                        autoeval_data = json.load(f)
                        item = autoeval_data[0] if isinstance(autoeval_data, list) and len(autoeval_data) > 0 else {}
                        rm_value = item.get("rm") if isinstance(item, dict) else None
                        
                        if rm_value is True:
                            task_success = True
                            successful_tasks += 1
                            if n_steps is not None: successful_steps.append(n_steps)
                            if score is not None: successful_scores.append(score)
                            if llm_data is not None: successful_llm_usage.append(llm_data)
                        else:
                            if n_steps is not None: failed_steps.append(n_steps)
                            if score is not None: failed_scores.append(score)
                            if llm_data is not None: failed_llm_usage.append(llm_data)
                except (json.JSONDecodeError, KeyError, IndexError):
                    if n_steps is not None: failed_steps.append(n_steps)
                    if score is not None: failed_scores.append(score)
                    if llm_data is not None: failed_llm_usage.append(llm_data)
            else:
                if n_steps is not None: failed_steps.append(n_steps)
                if score is not None: failed_scores.append(score)
                if llm_data is not None: failed_llm_usage.append(llm_data)
    
    # 计算统计信息
    success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
    total_err_tasks = tasks_with_errors + tasks_without_errors
    error_rate = tasks_with_errors / total_err_tasks if total_err_tasks > 0 else 0
    
    # 通用基础统计函数
    def calculate_basic_stats(data_list: List[float]) -> Dict:
        if not data_list:
            return {"count": 0, "mean": 0, "median": 0, "min": 0, "max": 0}
        sorted_data = sorted(data_list)
        n = len(data_list)
        return {
            "count": n,
            "mean": round(sum(data_list) / n, 4),
            "median": sorted_data[n // 2] if n % 2 == 1 else (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2,
            "min": min(data_list),
            "max": max(data_list)
        }
    
    # LLM 专用统计函数 (处理字典列表)
    def calculate_llm_stats(usage_list: List[Dict]) -> Dict:
        if not usage_list:
            return {}
        
        keys = ["total", "step1_solve", "step2_eval", "step3_cal", "step4_induce"]
        stats = {}
        for key in keys:
            values = [d[key] for d in usage_list]
            stats[key] = calculate_basic_stats(values)
        return stats

    return {
        "overall": {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": round(success_rate * 100, 2),
        },
        "step_statistics": {
            "all_tasks": calculate_basic_stats(all_steps),
            "successful_tasks": calculate_basic_stats(successful_steps),
            "failed_tasks": calculate_basic_stats(failed_steps)
        },
        "score_statistics": {
            "all_tasks": calculate_basic_stats(all_scores),
            "successful_tasks": calculate_basic_stats(successful_scores),
            "failed_tasks": calculate_basic_stats(failed_scores)
        },
        # 新增 LLM 统计
        "llm_statistics": {
            "all_tasks": calculate_llm_stats(all_llm_usage),
            "successful_tasks": calculate_llm_stats(successful_llm_usage),
            "failed_tasks": calculate_llm_stats(failed_llm_usage)
        },
        "error_statistics": {
            "tasks_with_errors": tasks_with_errors,
            "error_rate": round(error_rate * 100, 2),
            "error_messages": error_messages
        }
    }

def print_statistics(stats: Dict):
    """打印统计结果"""
    print("=" * 60)
    print("WebArena 任务运行结果统计")
    print("=" * 60)
    
    overall = stats["overall"]
    print(f"\n总体统计:")
    print(f"  总任务数: {overall['total_tasks']}")
    print(f"  成功任务数: {overall['successful_tasks']}")
    print(f"  成功率: {overall['success_rate']}%")
    
    def print_sub_stats(title, sub_stats):
        print(f"\n{title}:")
        if not sub_stats or sub_stats['count'] == 0:
            print("  无数据")
            return
        print(f"  数量: {sub_stats['count']} | 均值: {sub_stats['mean']} | 中位数: {sub_stats['median']} | Min/Max: {sub_stats['min']}/{sub_stats['max']}")

    # 步骤和分数
    print("\n" + "-"*20 + " 步骤数统计 (Steps) " + "-"*20)
    print_sub_stats("所有任务", stats["step_statistics"]["all_tasks"])
    print_sub_stats("成功任务", stats["step_statistics"]["successful_tasks"])
    
    print("\n" + "-"*20 + " 分数统计 (Score) " + "-"*20)
    print_sub_stats("所有任务", stats["score_statistics"]["all_tasks"])

    # --- LLM 调用统计 (新增) ---
    print("\n" + "-"*20 + " LLM 调用次数统计 " + "-"*20)
    llm_stats = stats["llm_statistics"]["all_tasks"]
    if llm_stats:
        print(f"  统计样本数: {llm_stats['total']['count']}")
        print(f"  [Total] 平均: {llm_stats['total']['mean']} (Max: {llm_stats['total']['max']})")
        print(f"  [Step1 Solve]  平均: {llm_stats['step1_solve']['mean']}")
        print(f"  [Step2 Eval]   平均: {llm_stats['step2_eval']['mean']} (包含自动修正)")
        print(f"  [Step3 Cal]    平均: {llm_stats['step3_cal']['mean']} (包含自动修正)")
        print(f"  [Step4 Induce] 平均: {llm_stats['step4_induce']['mean']}")
    else:
        print("  无 LLM 统计数据")

    # 错误信息
    print("\n" + "-"*20 + " 错误统计 " + "-"*20)
    print(f"  错误率: {stats['error_statistics']['error_rate']}%")
    if stats['error_statistics']['error_messages']:
        print(f"  首个错误示例: {stats['error_statistics']['error_messages'][0]['err_msg']}")

def save_statistics(stats: Dict, output_file: str = "analyze/webarena_statistics_admin_awm_v1_waber.json"):
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"\n统计结果已保存到: {output_file}")
    except Exception as e:
        print(f"保存统计结果时出错: {e}")

def main():
    print("正在分析WebArena运行结果...")
    # 假设 llm_info 文件夹在当前目录下，如果位置不同请修改此处
    try:
        stats = analyze_webarena_results()
        print_statistics(stats)
        save_statistics(stats)
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    main()