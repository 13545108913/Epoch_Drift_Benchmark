import json

# 定义输入和输出文件名
input_file = 'test.raw.json'
output_file = 'gitlab_tasks_processed.json'

try:
    # --- 1. 读取原始JSON文件 ---
    # 使用 utf-8 编码打开文件
    with open(input_file, 'r', encoding='utf-8') as f:
        all_tasks = json.load(f)

    print(f"成功读取 {input_file}，共 {len(all_tasks)} 个任务。")

    # --- 2. 筛选 "sites" 列表包含 "gitlab" 的任务 ---
    # 我们使用列表推导式来高效地完成筛选
    # task.get("sites", []) 是一种安全的写法，防止某个任务万一没有 "sites" 键
    gitlab_tasks = [
        task for task in all_tasks 
        if task.get("sites", []) == ["gitlab"]
    ]

    print(f"已筛选出 {len(gitlab_tasks)} 个 'gitlab' 相关任务。")

    # --- 3. 对筛选后的任务列表重新编号 "task_id" ---
    # 使用 enumerate 来获取新索引 (new_id)，它会从 0 开始
    for new_id, task in enumerate(gitlab_tasks):
        task["task_id"] = new_id
    
    print("已完成 'task_id' 的重新编号。")

    # --- 4. 将处理后的结果写入新的JSON文件 ---
    with open(output_file, 'w', encoding='utf-8') as f:
        # ensure_ascii=False 确保中文字符或特殊符号（如 ™）正确写入
        # indent=4 使输出的JSON文件格式化，易于阅读
        json.dump(gitlab_tasks, f, ensure_ascii=False, indent=4)

    print(f"处理完成！结果已保存到：{output_file}")

except FileNotFoundError:
    print(f"错误：未找到输入文件 '{input_file}'。")
    print("请确保该文件与Python脚本在同一目录下。")
except json.JSONDecodeError:
    print(f"错误：文件 '{input_file}' 格式不正确，无法解析为 JSON。")
except Exception as e:
    print(f"发生了一个意外错误：{e}")