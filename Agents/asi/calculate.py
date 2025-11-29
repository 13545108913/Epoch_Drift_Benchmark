import os
import json
from pathlib import Path
from typing import Dict, List, Tuple

def analyze_webarena_results(result_dir: str = "./results3") -> Dict:
    """
    分析WebArena任务运行结果
    
    Args:
        result_dir: 结果目录路径
        
    Returns:
        包含统计信息的字典
    """
    result_path = Path(result_dir)
    
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
    
    # 错误信息统计 (新增)
    error_messages = []  # 存储所有非null的错误信息
    tasks_with_errors = 0  # 有错误的task数量
    tasks_without_errors = 0  # 没有错误的task数量
    
    # 遍历结果目录
    for task_dir in result_path.iterdir():
        if task_dir.is_dir() and task_dir.name.startswith("myBenchmark.") and not task_dir.name.endswith("test"):
            task_id = task_dir.name.split(".")[1]
                
            total_tasks += 1
            # 检查是否存在 deepseek-chat_autoeval.json 文件
            autoeval_file = task_dir / "deepseek-chat_autoeval.json"
            summary_file = task_dir / "summary_info.json"
            
            # 获取步骤数、分数和错误信息
            n_steps = None
            score = None
            err_msg = None
            
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        
                        # 提取 Steps
                        n_steps = summary_data.get("n_steps")
                        if n_steps is not None:
                            all_steps.append(n_steps)
                            
                        # 提取 Score
                        raw_score = summary_data.get("cum_reward")
                        if raw_score is not None:
                            try:
                                score = float(raw_score) # 确保转换为数字
                                all_scores.append(score)
                            except (ValueError, TypeError):
                                print(f"警告: 任务 {task_id} 的 score 格式不正确: {raw_score}")
                                score = None

                        # 提取错误信息 (新增)
                        err_msg = summary_data.get("err_msg")
                        if err_msg is not None:
                            # err_msg不为null，表示有错误
                            tasks_with_errors += 1
                            error_messages.append({
                                "task_id": task_id,
                                "err_msg": err_msg
                            })
                        else:
                            # err_msg为null，表示没有错误
                            tasks_without_errors += 1

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"警告: 无法读取 {summary_file}: {e}")
            
            # 检查任务是否成功
            task_success = False
            if autoeval_file.exists():
                try:
                    with open(autoeval_file, 'r', encoding='utf-8') as f:
                        autoeval_data = json.load(f)
                        # 注意：具体结构可能是一个列表或字典，根据你之前的代码假设是一个列表
                        item = autoeval_data[0] if isinstance(autoeval_data, list) and len(autoeval_data) > 0 else {}
                        rm_value = item.get("rm") if isinstance(item, dict) else None
                        
                        if rm_value is True:
                            task_success = True
                            successful_tasks += 1
                            # 记录成功任务的数据
                            if n_steps is not None:
                                successful_steps.append(n_steps)
                            if score is not None:
                                successful_scores.append(score)
                        else:
                            # 记录失败任务的数据
                            if n_steps is not None:
                                failed_steps.append(n_steps)
                            if score is not None:
                                failed_scores.append(score)
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    print(f"警告: 无法读取 {autoeval_file}: {e}")
                    # 读取autoeval失败通常视为任务判断逻辑出错，这里按原逻辑归为失败处理
                    if n_steps is not None:
                        failed_steps.append(n_steps)
                    if score is not None:
                        failed_scores.append(score)
            else:
                # 没有 autoeval 文件，任务失败
                if n_steps is not None:
                    failed_steps.append(n_steps)
                if score is not None:
                    failed_scores.append(score)
    
    # 计算统计信息
    success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
    
    # 错误信息统计计算 (新增)
    total_err_tasks = tasks_with_errors + tasks_without_errors
    error_rate = tasks_with_errors / total_err_tasks if total_err_tasks > 0 else 0
    
    # 通用统计函数 (用于步骤和分数)
    def calculate_basic_stats(data_list: List[float]) -> Dict:
        if not data_list:
            return {"count": 0, "mean": 0, "median": 0, "min": 0, "max": 0}
        
        sorted_data = sorted(data_list)
        n = len(data_list)
        return {
            "count": n,
            "mean": sum(data_list) / n,
            "median": sorted_data[n // 2] if n % 2 == 1 else (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2,
            "min": min(data_list),
            "max": max(data_list)
        }
    
    # 返回统计结果
    return {
        "overall": {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": round(success_rate * 100, 2),
            "success_rate_decimal": round(success_rate, 4)
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
        # 新增错误信息统计
        "error_statistics": {
            "tasks_with_errors": tasks_with_errors,
            "tasks_without_errors": tasks_without_errors,
            "total_tasks_with_err_info": total_err_tasks,
            "error_rate": round(error_rate * 100, 2),
            "error_rate_decimal": round(error_rate, 4),
            "error_messages": error_messages  # 包含所有错误信息的列表
        },
        "detailed_counts": {
            "tasks_with_steps": len(all_steps),
            "tasks_with_scores": len(all_scores),
            "tasks_with_err_info": total_err_tasks,  # 新增
            "successful_with_steps": len(successful_steps),
            "failed_with_steps": len(failed_steps)
        }
    }

def print_statistics(stats: Dict):
    """打印统计结果"""
    print("=" * 60)
    print("WebArena 任务运行结果统计")
    print("=" * 60)
    
    overall = stats["overall"]
    step_stats = stats["step_statistics"]
    score_stats = stats["score_statistics"]
    error_stats = stats["error_statistics"]  # 新增
    
    print(f"\n总体统计:")
    print(f"  总任务数: {overall['total_tasks']}")
    print(f"  成功任务数: {overall['successful_tasks']}")
    print(f"  成功率: {overall['success_rate']}%")
    
    # --- 辅助打印函数 ---
    def print_sub_stats(title, sub_stats):
        print(f"\n{title}:")
        print(f"  记录数量: {sub_stats['count']}")
        if sub_stats['count'] > 0:
            print(f"  平均值: {sub_stats['mean']:.2f}")
            print(f"  中位数: {sub_stats['median']:.2f}")
            print(f"  最小值: {sub_stats['min']}")
            print(f"  最大值: {sub_stats['max']}")

    # --- 步骤统计 ---
    print("\n" + "-"*20 + " 步骤数统计 (Steps) " + "-"*20)
    print_sub_stats("所有任务步骤", step_stats["all_tasks"])
    print_sub_stats("成功任务步骤", step_stats["successful_tasks"])
    print_sub_stats("失败任务步骤", step_stats["failed_tasks"])

    # --- 分数统计 ---
    print("\n" + "-"*20 + " 分数统计 (Score) " + "-"*20)
    print_sub_stats("所有任务分数", score_stats["all_tasks"])
    print_sub_stats("成功任务分数", score_stats["successful_tasks"])
    print_sub_stats("失败任务分数", score_stats["failed_tasks"])

    # --- 错误信息统计 (新增) ---
    print("\n" + "-"*20 + " 错误信息统计 (Error Messages) " + "-"*20)
    print(f"  有错误的任务数: {error_stats['tasks_with_errors']}")
    print(f"  无错误的任务数: {error_stats['tasks_without_errors']}")
    print(f"  有错误信息记录的任务总数: {error_stats['total_tasks_with_err_info']}")
    print(f"  错误率: {error_stats['error_rate']}%")
    
    # 打印具体的错误信息
    if error_stats['error_messages']:
        print(f"\n  具体错误信息:")
        for i, error in enumerate(error_stats['error_messages'][:10], 1):  # 只显示前10个错误
            print(f"    {i}. 任务 {error['task_id']}: {error['err_msg']}")
        if len(error_stats['error_messages']) > 10:
            print(f"    ... 还有 {len(error_stats['error_messages']) - 10} 个错误信息")
    else:
        print(f"\n  无错误信息")

def save_statistics(stats: Dict, output_file: str = "webarena_statistics_gitlab_2.json"):
    """保存统计结果到JSON文件"""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"\n统计结果已保存到: {output_file}")
    except Exception as e:
        print(f"保存统计结果时出错: {e}")

def main():
    """主函数"""
    # 分析结果
    print("正在分析WebArena运行结果...")
    try:
        stats = analyze_webarena_results()
        # 打印统计结果
        print_statistics(stats)
        # 保存统计结果
        save_statistics(stats)
    except FileNotFoundError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"运行时发生未预期的错误: {e}")

if __name__ == "__main__":
    main()