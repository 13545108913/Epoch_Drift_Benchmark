import json

# --- 配置 ---

# 2. 输入文件（上一步生成的文件）
INPUT_FILE = 'benchmark_tasks.json'

# 3. 输出文件（最终的、已清理的文件）
OUTPUT_FILE = 'wordpress_tasks_final.json'

# --- 脚本开始 ---

def main():
    # 将列表转换为 set（集合），这样查找效率更高
    # 集合也会自动处理你列表中重复的ID

    print(f"--- 任务清理和重编号脚本 ---")

    try:
        # --- 1. 读取原始文件 ---
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            all_tasks = json.load(f)
        
        print(f"成功读取 {INPUT_FILE}，包含 {len(all_tasks)} 个任务。")

        cleaned_tasks = all_tasks

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