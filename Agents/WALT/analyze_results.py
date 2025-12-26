import os
import json
import glob
from statistics import mean
from pathlib import Path
from typing import List

# --- 配置路径 ---
BASE_DIR = "outputs/wa_shopping_admin_v2_drift"
PERFORMANCE_DIR = os.path.join(BASE_DIR, "performance")
TRAJECTORY_DIR = os.path.join(BASE_DIR, "trajectory")
KB_TOOLS_DIR = "walt-tools/shopping_admin"

# --- 1. 工具发现与加载模块 (保持不变) ---
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

def load_kb_functions(tool_dir: str) -> set:
    print(f"--- 正在从 {tool_dir} 加载知识库函数定义 ---")
    json_paths = _discover_tool_files(tool_dir)
    kb_functions = set()
    for path in json_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("name"): kb_functions.add(data.get("name"))
        except Exception: pass
    print(f"成功加载 {len(kb_functions)} 个知识库函数")
    return kb_functions

# --- 2. Performance 分析 (保持不变) ---
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

# --- 3. Trajectory 分析 (核心修改部分) ---
def analyze_trajectory(kb_functions: set):
    """
    分析 trajectory 数据，能够正确解析嵌套在 args['action'] 中的真实工具名。
    """
    print(f"--- 开始分析 Trajectory 数据 ({TRAJECTORY_DIR}) ---")
    
    json_files = glob.glob(os.path.join(TRAJECTORY_DIR, "*.json"))
    
    if not json_files:
        print("未找到 trajectory JSON 文件。")
        return

    step_counts = []
    task_tools_map = {} 
    kb_stats = {func: 0 for func in kb_functions}
    total_files_processed = 0

    for file_path in json_files:
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_files_processed += 1
                
                # 统计 Steps
                steps_data = data.get("steps", {})
                step_counts.append(len(steps_data))
                
                used_tools = []
                
                # 遍历 Step
                for step_id, step_content in steps_data.items():
                    # 安全获取 tool_calls 列表
                    tool_calls = step_content.get("output_messages", {}).get("tool_call_message", {}).get("tool_calls", [])
                    
                    if tool_calls:
                        for tool in tool_calls:
                            top_level_name = tool.get("name")
                            args = tool.get("args", {})
                            
                            # --- 核心修改：提取真实动作名 ---
                            real_action_names = []
                            
                            # 检查是否存在 args -> action 列表 (如 click_element, type, 或是嵌套的 kb_function)
                            actions_list = args.get("action", [])
                            if isinstance(actions_list, list) and actions_list:
                                for action_item in actions_list:
                                    if isinstance(action_item, dict):
                                        # 提取字典的所有键（通常只有一个，如 "click_element"）
                                        real_action_names.extend(action_item.keys())
                            
                            # 如果没在 action 列表里找到，则回退使用最外层的 name (例如可能是直接调用的 KB 函数)
                            if not real_action_names and top_level_name:
                                real_action_names.append(top_level_name)
                                
                            # --- 统计与记录 ---
                            for action_name in real_action_names:
                                # 1. 记录到工具链
                                used_tools.append(action_name)
                                # 2. 统计知识库函数调用
                                for kbf in kb_functions:
                                    if action_name in kbf or kbf in action_name:
                                        kb_stats[kbf] += 1
                                
                
                task_tools_map[file_name] = used_tools

        except Exception as e:
            print(f"读取文件 {file_name} 出错: {e}")

    # --- 输出结果 ---
    if step_counts:
        print(f"分析文件总数: {total_files_processed}")
        print(f"平均 Step 数: {mean(step_counts):.2f}")
        
        print("\n=== 知识库函数平均调用次数 (Per Task) ===")
        # 仅显示调用过的，或者全部显示
        sorted_kb_stats = sorted(kb_stats.items(), key=lambda x: x[1], reverse=True)
        
        print(f"{'函数名':<30} | {'总次数':<8} | {'平均次数/任务'}")
        print("-" * 65)
        for func_name, total_count in sorted_kb_stats:
            avg_count = total_count / total_files_processed
            # 只有当总次数 > 0 时才高亮显示 (可选逻辑)
            if total_count >= 0: 
                print(f"{func_name:<30} | {total_count:<8} | {avg_count:.4f}")
        print("-" * 65)

        tool_set = set()
        print("\n各任务工具调用详情 (前5个示例):")
        for task_file, tools in list(task_tools_map.items()): 
            # 简化显示：只显示非 click/scroll 的关键动作，或者显示全部
            # 这里显示全部，但去重连续的相同动作以精简
            clean_tools = []
            if tools:
                clean_tools = [tools[0]]
                tool_set.add(tools[0])
                for t in tools[1:]:
                    if t != clean_tools[-1]: clean_tools.append(t)
                    tool_set.add(t)
            
            # print(f"[{task_file}]: {', '.join(clean_tools)}")
        print(f"tool set: {tool_set}")
    else:
        print("没有有效的 trajectory 数据。")

if __name__ == "__main__":
    if os.path.exists(BASE_DIR):
        kb_funcs = load_kb_functions(KB_TOOLS_DIR)
        analyze_performance()
        analyze_trajectory(kb_funcs)
    else:
        print(f"错误：找不到路径 {BASE_DIR}")