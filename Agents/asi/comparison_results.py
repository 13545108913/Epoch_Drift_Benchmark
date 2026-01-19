import os
import json
from pathlib import Path
from typing import Set, Dict, List

# --- 配置路径 ---
DIR_V1_TRAIN = "gitlab_results/results_v12_train"
DIR_V2_DRIFT = "gitlab_results/results_v16"
OUTPUT_FILE = "analyze/comparison_results.json"

def get_task_status(result_dir: str) -> Dict[str, Set[str]]:
    """
    遍历结果目录，返回成功和失败的任务ID集合。
    
    Returns:
        Dict with keys: 'success', 'failed', 'all'
    """
    result_path = Path(result_dir)
    success_ids = set()
    failed_ids = set()
    all_ids = set()

    if not result_path.exists():
        print(f"警告: 目录 {result_dir} 不存在")
        return {"success": set(), "failed": set(), "all": set()}

    print(f"正在扫描目录: {result_dir} ...")

    for task_dir in result_path.iterdir():
        # 筛选符合 myBenchmark.xxx 格式的文件夹，且不包含 test
        if task_dir.is_dir() and task_dir.name.startswith("myBenchmark.") and not task_dir.name.endswith("test"):
            try:
                task_id = task_dir.name.split(".")[1]
                all_ids.add(task_id)

                # 寻找自动评估文件 (匹配任何以 _autoeval.json 结尾的文件)
                # 优先寻找 deepseek-chat_autoeval.json，如果不存在则找任意一个
                autoeval_file = task_dir / "summary_info.json"
                
                is_success = False
                if autoeval_file.exists():
                    try:
                        with open(autoeval_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # WebArena 标准格式: [{"rm": true, ...}] 或 {"rm": true}
                            item = data[0] if isinstance(data, list) and len(data) > 0 else data
                            if isinstance(item, dict) and item.get("cum_reward") == 1.0:
                                is_success = True
                    except Exception:
                        pass # 读取失败视为任务失败

                if is_success:
                    success_ids.add(task_id)
                else:
                    failed_ids.add(task_id)

            except IndexError:
                continue

    return {
        "success": success_ids,
        "failed": failed_ids,
        "all": all_ids
    }

def save_comparison(data: dict, filename: str):
    try:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        # 将 set 转换为 list 以便 JSON 序列化
        json_ready = {k: sorted(list(v)) for k, v in data.items()}
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_ready, f, indent=2, ensure_ascii=False)
        print(f"\n详细对比结果已保存至: {filename}")
    except Exception as e:
        print(f"保存失败: {e}")

def main():
    # 1. 获取两组实验的结果
    results_v1 = get_task_status(DIR_V1_TRAIN)
    results_v2 = get_task_status(DIR_V2_DRIFT)

    if not results_v1["all"] or not results_v2["all"]:
        print("错误: 未找到足够的实验数据进行对比。")
        return

    # 2. 计算集合关系
    # 共同参与的任务（取交集，确保只比较两者都运行过的任务，或者根据需求比较全集）
    # 这里我们对比所有涉及的任务ID
    
    s1 = results_v1["success"]
    s2 = results_v2["success"]
    f1 = results_v1["failed"]
    f2 = results_v2["failed"]

    # 逻辑定义：
    # 两者都成功: ID 在 s1 且 在 s2
    both_success = s1 & s2
    
    # 两者都失败: (ID 在 f1 且 在 f2) 或者 (ID 在 f1 且 V2中未运行) -> 广义的都失败
    # 但为了严谨，我们通常只统计 "两者都判定为失败" 的任务
    # 注意：如果某任务在V1成功，在V2没运行(不存在)，它会被归类为 "Only V1 Success"
    both_failed = f1 & f2

    # 只有前者成功: 在 s1 中，但不在 s2 中 (即在V2中失败或未运行)
    only_v1_success = s1 - s2

    # 只有后者成功: 在 s2 中，但不在 s1 中
    only_v2_success = s2 - s1

    # 3. 输出统计
    print("\n" + "="*50)
    print("WebArena 实验结果对比报告")
    print("="*50)
    print(f"实验 1 (Train): {DIR_V1_TRAIN}")
    print(f"  - 总任务: {len(results_v1['all'])}")
    print(f"  - 成功: {len(s1)} | 失败: {len(f1)}")
    
    print(f"\n实验 2 (Drift): {DIR_V2_DRIFT}")
    print(f"  - 总任务: {len(results_v2['all'])}")
    print(f"  - 成功: {len(s2)} | 失败: {len(f2)}")

    print("-" * 50)
    print(f"✅ 两者都成功 (Both Success): {len(both_success)}")
    print(f"❌ 两者都失败 (Both Failed):  {len(both_failed)}")
    print(f"⬅️ 仅 V1 成功 (V1 Success / V2 Failed): {len(only_v1_success)}")
    print(f"➡️ 仅 V2 成功 (V1 Failed / V2 Success): {len(only_v2_success)}")
    print("-" * 50)

    # 4. 打印具体 ID (如果数量不多，打印全部；否则打印前10个)
    def print_ids(title, ids):
        id_list = sorted(list(ids), key=lambda x: int(x) if x.isdigit() else x)
        print(f"\n{title} (Total: {len(id_list)}):")
        if len(id_list) > 20:
            print(f"  {', '.join(id_list[:20])} ... (还有 {len(id_list)-20} 个)")
        elif len(id_list) > 0:
            print(f"  {', '.join(id_list)}")
        else:
            print("  (无)")

    print_ids("仅 V1 成功 (退化任务?)", only_v1_success)
    print_ids("仅 V2 成功 (改进任务?)", only_v2_success)

    # 5. 保存文件
    save_data = {
        "both_success": both_success,
        "both_failed": both_failed,
        "only_v1_train_success": only_v1_success,
        "only_v2_drift_success": only_v2_success,
        "raw_stats": {
            "v1_total": len(results_v1['all']),
            "v1_success_count": len(s1),
            "v2_total": len(results_v2['all']),
            "v2_success_count": len(s2)
        }
    }
    # save_comparison(save_data, OUTPUT_FILE)

if __name__ == "__main__":
    main()
