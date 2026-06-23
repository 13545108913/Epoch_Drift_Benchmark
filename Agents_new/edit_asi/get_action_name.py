import ast
import os
import glob
import re

def get_function_names(file_path):
    """
    解析 Python 文件并获取所有函数名（静态分析）
    """
    if not os.path.exists(file_path):
        print(f"错误: 找不到文件 {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8") as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError as e:
            print(f"解析错误 {file_path}: {e}")
            return []
    
    function_names = []
    
    # 遍历语法树中的所有节点
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_names.append(node.name)
            
    return function_names

def calculate_average_calls(target_py_file, results_dir):
    """
    统计指定 Python 文件中的函数在实验日志中出现的平均次数
    """
    # 1. 获取目标文件中的所有函数名
    func_names = get_function_names(target_py_file)
    if not func_names:
        print("未找到函数定义或文件为空。")
        return

    print(f"在 '{target_py_file}' 中找到 {len(func_names)} 个函数。正在分析日志...")

    # 初始化计数器：{函数名: 总调用次数}
    total_counts = {name: 0 for name in func_names}
    valid_task_count = 0

    # 2. 查找符合 pattern 的所有文件夹 (results/myBenchmark.x)
    # 使用 glob 匹配路径模式
    search_pattern = os.path.join(results_dir, "myBenchmark.*")
    potential_dirs = glob.glob(search_pattern)

    for folder in potential_dirs:
        # 确认 .x 后缀是否为整数
        folder_name = os.path.basename(folder)
        try:
            suffix = folder_name.split('.')[-1]
            int(suffix) # 尝试转换为整数，如果失败会抛出 ValueError
        except (ValueError, IndexError):
            continue # 跳过不符合 myBenchmark.整数 格式的文件夹

        log_path = os.path.join(folder, "experiment.log")
        
        # 3. 读取日志并统计
        if os.path.exists(log_path):
            valid_task_count += 1
            try:
                with open(log_path, "r", encoding="utf-8", errors='ignore') as f:
                    content = f.read()
                    
                    # 遍历所有函数名，精确匹配被反引号包围的调用
                    for name in func_names:
                        # 构造精确匹配该函数调用的正则表达式：
                        # ```[函数名](...)' 
                        # re.escape(name) 处理函数名中可能存在的特殊字符
                        # .*? 匹配函数名后的任意参数，非贪婪模式
                        # re.DOTALL 确保 '.' 匹配换行符，因为 ``` 块可能跨多行
                        pattern = rf"```\s*{re.escape(name)}\s*\([^`]*?\)\s*```"
                        
                        # 查找所有匹配项
                        matches = re.findall(pattern, content, re.DOTALL)
                        
                        count = len(matches)
                        total_counts[name] += count
            except Exception as e:
                print(f"无法读取日志 {log_path}: {e}")

    # 4. 计算平均值并输出结果
    if valid_task_count == 0:
        print("未找到有效的任务日志文件 (experiment.log)。")
        return

    print(f"\n--- 统计结果 (共分析了 {valid_task_count} 个任务) ---")
    print(f"{'Function Name':<30} | {'Total Calls':<12} | {'Avg Calls/Task':<15}")
    print("-" * 65)

    # 排序：按平均调用次数从高到低排序
    sorted_stats = sorted(total_counts.items(), key=lambda item: item[1], reverse=True)
    tmp = 0
    for name, total in sorted_stats:
        # 计算平均值
        avg = total / valid_task_count
        tmp += total
        if total > 0: # 仅显示被调用过的函数，如果想显示所有函数请去掉此判断
            print(f"{name:<30} | {total:<12} | {avg:<15.2f}")
    print(f"平均：{(tmp / valid_task_count):<15.3f}")

# --- 执行脚本 ---
if __name__ == "__main__":
    # 配置路径
    TARGET_FILE = 'actions/admin.py'
    RESULTS_DIR = 'results'

    calculate_average_calls(TARGET_FILE, RESULTS_DIR)