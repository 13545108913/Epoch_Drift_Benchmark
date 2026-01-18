import os
import json
import glob
from typing import Dict, Set

# --- 配置路径 ---
# 前者 (Baseline / 旧版本)
BASE_DIR_1 = "outputs_admin/wa_shopping_admin_v1" 

# 后者 (Target / 新版本) - 请在此处填入第二个目录路径
BASE_DIR_2 = "outputs_admin/wa_shopping_admin_v2_3" 

def load_task_scores(base_dir: str) -> Dict[str, float]:
    """
    读取指定 BASE_DIR 下 performance 目录中的所有任务分数。
    返回: {filename: score}
    """
    performance_dir = os.path.join(base_dir, "performance")
    task_scores = {}
    
    if not os.path.exists(performance_dir):
        print(f"警告: 目录不存在 - {performance_dir}")
        return task_scores

    json_files = glob.glob(os.path.join(performance_dir, "*.json"))
    
    for file_path in json_files:
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 默认获取 score，如果没有则默认为 0.0
                score = data.get("score", 0.0)
                task_scores[file_name] = score
        except Exception as e:
            print(f"读取文件错误 {file_name}: {e}")
            
    return task_scores

def compare_runs(dir1: str, dir2: str):
    print(f"=== 对比任务结果 ===")
    print(f"BASE 1 (前者): {dir1}")
    print(f"BASE 2 (后者): {dir2}")
    print("-" * 60)

    # 1. 加载数据
    scores_1 = load_task_scores(dir1)
    scores_2 = load_task_scores(dir2)

    # 2. 找出共同存在的任务文件
    files_1 = set(scores_1.keys())
    files_2 = set(scores_2.keys())
    common_files = files_1.intersection(files_2)
    
    missing_in_2 = files_1 - files_2
    missing_in_1 = files_2 - files_1

    if not common_files:
        print("错误: 两个目录下没有找到同名的任务文件，无法进行对比。")
        return

    # 3. 分类列表
    regressed_tasks = [] # 1成功 -> 2失败
    improved_tasks = []  # 1失败 -> 2成功
    both_success = []
    both_failed = []

    # 4. 遍历对比
    for file_name in common_files:
        s1 = scores_1[file_name]
        s2 = scores_2[file_name]

        # 定义成功判定标准 (通常 score == 1.0 为成功)
        is_success_1 = (s1 == 1.0)
        is_success_2 = (s2 == 1.0)

        if is_success_1 and not is_success_2:
            regressed_tasks.append((file_name, s1, s2))
        elif not is_success_1 and is_success_2:
            improved_tasks.append((file_name, s1, s2))
        elif is_success_1 and is_success_2:
            both_success.append(file_name)
        else:
            both_failed.append(file_name)

    # --- 5. 输出结果 ---

    # A. 概览
    print(f"\n📊 概览统计 (共 {len(common_files)} 个共同任务):")
    print(f"  🔴 变差 (Success -> Fail): {len(regressed_tasks)}")
    print(f"  🟢 变好 (Fail -> Success): {len(improved_tasks)}")
    print(f"  ⚪ 持平 (Both Success)   : {len(both_success)}")
    print(f"  ⚫ 持平 (Both Failed)    : {len(both_failed)}")
    
    if missing_in_2:
        print(f"  ⚠️  BASE 2 缺失文件数    : {len(missing_in_2)}")
    if missing_in_1:
        print(f"  ⚠️  BASE 1 缺失文件数    : {len(missing_in_1)}")

    # B. 详细列表：前者成功，后者失败
    if regressed_tasks:
        print("\n" + "="*60)
        print(f"🔴 [退步任务] 前者成功 (1.0) -> 后者失败 (<1.0) (共 {len(regressed_tasks)} 个)")
        print(f"{'文件名':<50} | {'Base1':<6} -> {'Base2':<6}")
        print("-" * 60)
        for name, s1, s2 in sorted(regressed_tasks):
            print(f"{name:<50} | {s1:<6} -> {s2:<6}")

    # C. 详细列表：前者失败，后者成功
    if improved_tasks:
        print("\n" + "="*60)
        print(f"🟢 [改进任务] 前者失败 (<1.0) -> 后者成功 (1.0) (共 {len(improved_tasks)} 个)")
        print(f"{'文件名':<50} | {'Base1':<6} -> {'Base2':<6}")
        print("-" * 60)
        for name, s1, s2 in sorted(improved_tasks):
            print(f"{name:<50} | {s1:<6} -> {s2:<6}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    # 确保填入了两个路径，如果路径相同或为空会提示
    if BASE_DIR_1 and BASE_DIR_2 and BASE_DIR_1 != BASE_DIR_2:
        compare_runs(BASE_DIR_1, BASE_DIR_2)
    else:
        print("请在代码顶部配置两个不同的 BASE_DIR 路径。")