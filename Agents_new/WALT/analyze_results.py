import os
import json
import glob
from statistics import mean
from pathlib import Path
from typing import List

# --- 配置路径 ---
BASE_DIR = "outputs/wa_gitlab_v16_waber"
PERFORMANCE_DIR = os.path.join(BASE_DIR, "performance")
TRAJECTORY_DIR = os.path.join(BASE_DIR, "trajectory_simplified")
KB_TOOLS_DIR = "walt-tools/gitlab_v12"

# --- 辅助函数：名称归一化 (核心修复) ---
def normalize_name(name: str) -> str:
    """
    将工具名称标准化，以便匹配 workflow_xxx.v2 和 tool_xxx。
    例如：
    'workflow_search_products.v2' -> 'search_products'
    'tool_search_products'        -> 'search_products'
    """
    if not name: return ""
    # 转小写
    name = name.lower()
    # 去除版本号 (假设格式为 .v数字)
    if ".v" in name:
        parts = name.split(".v")
        # 简单判断只要后面跟的是数字就截断
        if len(parts) > 1 and parts[-1].split('.')[0].isdigit():
            name = parts[0]
            
    # 去除常见前缀
    prefixes = ["workflow_", "tool_", "magentoadmin_", "admin_", "MagentoAdmin_", "gitlab_"]
    for p in prefixes:
        if name.startswith(p):
            name = name.replace(p, "", 1) # 只替换第一个匹配
            break
            
    return name.strip()

# --- 1. 工具发现与加载模块 ---
def _discover_tool_files(tool_dir: str, tool_type: str = "base") -> List[Path]:
    tool_path = Path(tool_dir)
    if not tool_path.exists():
        return []
    tool_files = []
    tools_found = {}
    for subdir in tool_path.iterdir():
        if subdir.is_dir() and subdir.name not in ["logs", "exclude"]:
            tool_name = subdir.name
            tools_found[tool_name] = {"optimized": None, "base": None}
            for optimized_file in subdir.glob("*.optimized.json"):
                stem = optimized_file.stem
                if ".v" in stem and len(stem.split(".v")) > 1 and stem.split(".v")[1].split(".")[0].isdigit(): continue
                tools_found[tool_name]["optimized"] = optimized_file
                break 
            for base_file in subdir.glob("*.tool.json"):
                stem = base_file.stem
                if ".v" in stem and len(stem.split(".v")) > 1 and stem.split(".v")[1].split(".")[0].isdigit(): continue
                tools_found[tool_name]["base"] = base_file
                break
    for tool_name, files in tools_found.items():
        if tool_type == "optimized":
            if files["optimized"]: tool_files.append(files["optimized"])
            elif files["base"]: tool_files.append(files["base"])
        else:
            if files["base"]: tool_files.append(files["base"])
    return tool_files

def load_kb_functions(tool_dir: str) -> dict:
    """
    返回字典: { '原始名称': '归一化名称' }
    """
    print(f"--- 正在从 {tool_dir} 加载知识库函数定义 ---")
    json_paths = _discover_tool_files(tool_dir)
    kb_functions = {} # Key: Original Name, Value: Normalized Name
    for path in json_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                original_name = data.get("name")
                if original_name: 
                    kb_functions[original_name] = normalize_name(original_name)
        except Exception: pass
    print(f"成功加载 {len(kb_functions)} 个知识库函数")
    return kb_functions

# --- 2. Performance 分析 ---
def analyze_performance():
    print(f"--- 开始分析 Performance 数据 ({PERFORMANCE_DIR}) ---")
    json_files = glob.glob(os.path.join(PERFORMANCE_DIR, "*.json"))
    if not json_files: return
    scores, input_tokens, file_count = [], [], 0
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                scores.append(data.get("score", 0.0))
                input_tokens.append(data.get("usage", {}).get("browser_agent_usage", {}).get("total_prompt_tokens", 0))
                file_count += 1
        except Exception: pass
    if file_count > 0:
        print(f"分析文件: {file_count} | 平均 Score: {mean(scores):.4f} | 平均 Tokens: {mean(input_tokens):.2f} | 数量: {file_count * mean(scores)}")
    print("-" * 30 + "\n")

# --- 3. Trajectory 分析 ---
def analyze_trajectory(kb_functions_map: dict):
    """
    kb_functions_map: {原始KB名: 归一化KB名}
    """
    print(f"--- 开始分析 Trajectory 数据 ({TRAJECTORY_DIR}) ---")
    
    json_files = glob.glob(os.path.join(TRAJECTORY_DIR, "*.json"))
    
    if not json_files:
        print("未找到 trajectory JSON 文件。")
        return

    step_counts = []
    task_tools_map = {} 
    # 初始化统计：使用原始名称作为Key，以便最后显示
    kb_stats = {k: 0 for k in kb_functions_map.keys()}
    total_files_processed = 0

    for file_path in json_files:
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_files_processed += 1
                
                # 1. 统计 Steps
                simplified_steps = data.get("simplified_steps", [])
                total_steps = data.get("total_steps")
                if total_steps is not None:
                    step_counts.append(total_steps)
                else:
                    step_counts.append(len(simplified_steps))
                
                used_tools = []
                
                # 2. 遍历 Steps 提取 Action
                for step in simplified_steps:
                    actions = step.get("action", [])
                    if isinstance(actions, list):
                        for action_name in actions:
                            used_tools.append(action_name)
                            
                            # 3. 模糊匹配统计
                            # 归一化当前的 action
                            current_action_norm = normalize_name(action_name)
                            
                            # 遍历 KB Map 寻找匹配
                            # 逻辑：如果 归一化后的KB名 == 归一化后的Action名
                            matched = False
                            for kb_orig, kb_norm in kb_functions_map.items():
                                if kb_norm == current_action_norm:
                                    kb_stats[kb_orig] += 1
                                    matched = True
                                    # 注意：这里break意味着一个action只归属到一个KB函数。
                                    # 如果有重名(v2, v3同时存在且归一化相同)，可能会只加到其中一个，
                                    # 视字典顺序而定。通常没问题。
                                    break 
                
                task_tools_map[file_name] = used_tools

        except Exception as e:
            print(f"读取文件 {file_name} 出错: {e}")

    # --- 输出结果 ---
    if step_counts:
        print(f"分析文件总数: {total_files_processed}")
        print(f"平均 Step 数: {mean(step_counts):.2f}")

        # === 新增统计逻辑 ===
        total_kb_calls_all_tasks = sum(kb_stats.values())
        avg_kb_calls_per_task = total_kb_calls_all_tasks / total_files_processed if total_files_processed else 0
        
        print(f"\n>>> 知识库工具总平均调用次数: {avg_kb_calls_per_task:.4f} (总调用: {total_kb_calls_all_tasks}) <<<")
        # ==================
        
        print("\n=== 知识库函数平均调用次数 (Per Task) ===")
        # 排序：按调用总次数降序
        sorted_kb_stats = sorted(kb_stats.items(), key=lambda x: x[1], reverse=True)
        
        print(f"{'函数名 (Raw)':<45} | {'总次数':<8} | {'平均次数/任务'}")
        print("-" * 80)
        for func_name, total_count in sorted_kb_stats:
            avg_count = total_count / total_files_processed
            # 只显示非零的，或者显示全部
            if total_count >= 0: 
                print(f"{func_name:<45} | {total_count:<8} | {avg_count:.4f}")
        print("-" * 80)

        tool_set = set()
        print("\n各任务工具调用详情 (前5个示例):")
        example_count = 0
        for task_file, tools in task_tools_map.items(): 
            if example_count >= 5: break
            
            clean_tools = []
            if tools:
                clean_tools = [tools[0]]
                tool_set.add(tools[0])
                for t in tools[1:]:
                    if t != clean_tools[-1]: clean_tools.append(t)
                    tool_set.add(t)
            else:
                for t in tools: tool_set.add(t)

            for t in tools: tool_set.add(t)

            print(f"[{task_file}]: {', '.join(clean_tools)}")
            example_count += 1
            
        print(f"\n检测到的所有工具集合: {tool_set}")
    else:
        print("没有有效的 trajectory 数据。")

if __name__ == "__main__":
    if os.path.exists(BASE_DIR):
        # 加载 KB 定义 (现在返回字典)
        kb_funcs_map = load_kb_functions(KB_TOOLS_DIR)
        analyze_performance()
        analyze_trajectory(kb_funcs_map)
    else:
        print(f"错误：找不到路径 {BASE_DIR}")