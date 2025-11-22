import os
import json
from pathlib import Path
from typing import Dict, List, Tuple

def analyze_webarena_results(result_dir: str = "./results") -> Dict:
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
    all_steps = []
    successful_steps = []
    failed_steps = []
    
    # 遍历结果目录
    for task_dir in result_path.iterdir():
        if task_dir.is_dir() and task_dir.name.startswith("myBenchmark.") and not task_dir.name.endswith("test"):
            task_id = task_dir.name.split(".")[1]
                
            total_tasks += 1
            # 检查是否存在 deepseek-chat_autoeval.json 文件
            autoeval_file = task_dir / "deepseek-chat_autoeval.json"
            summary_file = task_dir / "summary_info.json"
            
            # 获取步骤数
            n_steps = None
            if summary_file.exists():
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        n_steps = summary_data.get("n_steps")
                        if n_steps is not None:
                            all_steps.append(n_steps)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"警告: 无法读取 {summary_file}: {e}")
            
            # 检查任务是否成功
            task_success = False
            if autoeval_file.exists():
                try:
                    with open(autoeval_file, 'r', encoding='utf-8') as f:
                        autoeval_data = json.load(f)
                        rm_value = autoeval_data[0].get("rm")
                        if rm_value is True:
                            task_success = True
                            successful_tasks += 1
                            if n_steps is not None:
                                successful_steps.append(n_steps)
                        else:
                            if n_steps is not None:
                                failed_steps.append(n_steps)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"警告: 无法读取 {autoeval_file}: {e}")
                    if n_steps is not None:
                        failed_steps.append(n_steps)
            else:
                # 没有 autoeval 文件，任务失败
                if n_steps is not None:
                    failed_steps.append(n_steps)
    
    # 计算统计信息
    success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
    
    # 步骤统计
    def calculate_step_stats(steps: List[int]) -> Dict:
        if not steps:
            return {"count": 0, "mean": 0, "median": 0, "min": 0, "max": 0}
        
        sorted_steps = sorted(steps)
        n = len(steps)
        return {
            "count": n,
            "mean": sum(steps) / n,
            "median": sorted_steps[n // 2] if n % 2 == 1 else (sorted_steps[n // 2 - 1] + sorted_steps[n // 2]) / 2,
            "min": min(steps),
            "max": max(steps)
        }
    
    # 返回统计结果
    return {
        "overall": {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate": round(success_rate * 100, 2),  # 百分比形式
            "success_rate_decimal": round(success_rate, 4)  # 小数形式
        },
        "step_statistics": {
            "all_tasks": calculate_step_stats(all_steps),
            "successful_tasks": calculate_step_stats(successful_steps),
            "failed_tasks": calculate_step_stats(failed_steps)
        },
        "detailed_counts": {
            "tasks_with_steps": len(all_steps),
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
    
    print(f"\n总体统计:")
    print(f"  总任务数: {overall['total_tasks']}")
    print(f"  成功任务数: {overall['successful_tasks']}")
    print(f"  成功率: {overall['success_rate']}%")
    
    print(f"\n步骤数量统计 (所有任务):")
    all_stats = step_stats["all_tasks"]
    print(f"  有步骤记录的任务数: {all_stats['count']}")
    if all_stats['count'] > 0:
        print(f"  平均步骤数: {all_stats['mean']:.2f}")
        print(f"  中位数步骤数: {all_stats['median']:.2f}")
        print(f"  最小步骤数: {all_stats['min']}")
        print(f"  最大步骤数: {all_stats['max']}")
    
    print(f"\n步骤数量统计 (成功任务):")
    success_stats = step_stats["successful_tasks"]
    print(f"  有步骤记录的成功任务数: {success_stats['count']}")
    if success_stats['count'] > 0:
        print(f"  平均步骤数: {success_stats['mean']:.2f}")
        print(f"  中位数步骤数: {success_stats['median']:.2f}")
        print(f"  最小步骤数: {success_stats['min']}")
        print(f"  最大步骤数: {success_stats['max']}")
    
    print(f"\n步骤数量统计 (失败任务):")
    failed_stats = step_stats["failed_tasks"]
    print(f"  有步骤记录的失败任务数: {failed_stats['count']}")
    if failed_stats['count'] > 0:
        print(f"  平均步骤数: {failed_stats['mean']:.2f}")
        print(f"  中位数步骤数: {failed_stats['median']:.2f}")
        print(f"  最小步骤数: {failed_stats['min']}")
        print(f"  最大步骤数: {failed_stats['max']}")

def save_statistics(stats: Dict, output_file: str = "webarena_statistics_gitlab_drift.json"):
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
    stats = analyze_webarena_results()
    
    # 打印统计结果
    print_statistics(stats)
    
    # 保存统计结果
    save_statistics(stats)
        


if __name__ == "__main__":
    main()