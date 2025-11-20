import json

# --- 配置 ---

# 1. 你提供的有错误的 task_id 列表
ERROR_IDS_TO_REMOVE = [
    6, 20, 21, 23, 25, 26, 28, 56, 56, 57, 57, 58, 58, 
    136, 161, 162, 164
]

# 2. 输入文件（上一步生成的文件）
INPUT_FILE = 'gitlab_tasks_processed.json'

# 3. 输出文件（最终的、已清理的文件）
OUTPUT_FILE = 'gitlab_tasks_final.json'

# --- 脚本开始 ---

def main():
    # 将列表转换为 set（集合），这样查找效率更高
    # 集合也会自动处理你列表中重复的ID
    error_id_set = set(ERROR_IDS_TO_REMOVE)
    
    print(f"--- 任务清理和重编号脚本 ---")
    print(f"将从 {INPUT_FILE} 中移除 {len(error_id_set)} 个唯一的错误ID。")

    try:
        # --- 1. 读取原始文件 ---
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            all_tasks = json.load(f)
        
        print(f"成功读取 {INPUT_FILE}，包含 {len(all_tasks)} 个任务。")

        # --- 2. 过滤任务 ---
        # 使用列表推导式，只保留 task_id 不在 error_id_set 中的任务
        cleaned_tasks = [
            task for task in all_tasks 
            if task.get('task_id') not in error_id_set
        ]
        
        removed_count = len(all_tasks) - len(cleaned_tasks)
        print(f"已过滤任务：移除了 {removed_count} 个任务。")
        print(f"剩余 {len(cleaned_tasks)} 个有效任务。")

        # --- 3. 重新编号 ---
        for new_id, task in enumerate(cleaned_tasks):
            task['task_id'] = new_id
        
        print(f"已对剩余任务的 'task_id' 从 0 到 {len(cleaned_tasks) - 1} 重新编号。")

        # --- 4. 写入新文件 ---
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned_tasks, f, ensure_ascii=False, indent=4)
        
        print(f"\n--- 处理完成 ---")
        print(f"最终的、已清理的任务列表已保存到：{OUTPUT_FILE}")

    except FileNotFoundError:
        print(f"[错误] 未找到输入文件 '{INPUT_FILE}'。")
        print("请确保该文件与此脚本在同一目录下。")
    except json.JSONDecodeError:
        print(f"[错误] 文件 '{INPUT_FILE}' 格式不正确，无法解析为 JSON。")
    except Exception as e:
        print(f"发生了一个意外错误：{e}")

if __name__ == "__main__":
    main()