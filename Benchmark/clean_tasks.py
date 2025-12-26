import json

def compare_intents():
    file_v1 = 'admin_tasks_final_v1.json'
    file_v2 = 'admin_tasks_final_v2.json'

    try:
        print(f"正在读取文件...")
        with open(file_v1, 'r', encoding='utf-8') as f1:
            tasks_v1 = json.load(f1)
        with open(file_v2, 'r', encoding='utf-8') as f2:
            tasks_v2 = json.load(f2)

        # 1. 建立索引映射 {task_id: intent}
        # 这样即使两个文件里任务的顺序不同，也能正确找到同一个任务
        map_v1 = {task['task_id']: task.get('intent', '') for task in tasks_v1}
        map_v2 = {task['task_id']: task.get('intent', '') for task in tasks_v2}

        # 2. 找出共同存在的 ID (只有两个文件里都有的任务才能对比)
        common_ids = set(map_v1.keys()) & set(map_v2.keys())
        
        diff_ids = []

        print("-" * 50)
        print("差异详情 (Diff Details):")

        # 3. 遍历并对比
        for tid in sorted(list(common_ids)):
            intent_1 = map_v1[tid]
            intent_2 = map_v2[tid]

            # 严格对比字符串是否相等
            if intent_1 != intent_2:
                diff_ids.append(tid)
                print(f"\n[Task ID: {tid}]")
                print(f"  v1: {intent_1}")
                print(f"  v2: {intent_2}")

        # 4. 输出最终 ID 列表
        print("\n" + "=" * 50)
        if not diff_ids:
            print("结果：所有共同任务的 intent 均完全一致。")
        else:
            print(f"结果：发现 {len(diff_ids)} 个任务的 intent 不一样。")
            print("不一致的任务 ID 列表：")
            print(sorted(diff_ids))

    except FileNotFoundError as e:
        print(f"错误：找不到文件。{e}")
    except Exception as e:
        print(f"发生未知错误: {e}")

if __name__ == "__main__":
    compare_intents()