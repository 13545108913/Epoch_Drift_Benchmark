import json
import os  # 需要引入 os 来检查文件是否存在
import traceback
try:
    import fcntl
except ImportError:
    fcntl = None
from pathlib import Path
from dataclasses import asdict
from typing import Dict, Any, Tuple, List

from model import LLM
from log import AgentLogger
from monitor import Monitor
from prompt.system_prompt import sys_memory_prompt_template
from utils import remove_accessibility_tree_in_the_history, remove_browser_state_in_the_history, \
    create_message, deep_update, dict_to_outline_str, pretty_print_trajectory, remove_python_code_in_the_history

class MemoryManager:
    def __init__(self, memory_dir: str, logger: AgentLogger, output_dir: Path, sys_prompt_template: str, tool_schema_texts: str, use_memory: bool = True):
        self.memory_dir = Path(memory_dir)
        self.logger = logger
        self.output_dir: Path = output_dir
        self.sys_prompt_template = sys_prompt_template
        self.tool_schema_texts = tool_schema_texts
        self.use_memory = use_memory

        self.history: List[dict] = []

        self.tool_enhance_dict: Dict[str, Any] = self._load_memory(self.memory_dir / "tool_memory.json")
        self.application_enhance_dict: Dict[str, Any] = self._load_memory(self.memory_dir / "procedural_memory.json")
        self.methodology_enhance_dict: Dict[str, Any] = self._load_memory(self.memory_dir / "strategic_memory.json")

        self.app_guide_str = dict_to_outline_str(self.application_enhance_dict)
        self.metho_guide_str = dict_to_outline_str(self.methodology_enhance_dict)

        def _memory_loading_log(items: List[tuple]):
            for content, title in items:
                self.logger.log_task(str(content), subtitle="LOADING······", title=f"Load {title} Memory")

        _memory_loading_log([
            (self.tool_enhance_dict, "Tool"),
            (self.app_guide_str, "Application"),
            (self.metho_guide_str, "Methodology")
        ])

        self.update_system_prompt()

    @staticmethod
    def _load_memory(memory_path: Path) -> dict:
        try:
            if not memory_path.exists():
                return {}
            # 使用共享锁 (LOCK_SH) 读取
            with open(memory_path, "r", encoding="utf-8") as f:
                if fcntl:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                        text = f.read()
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                else:
                    text = f.read()

                if not text.strip():
                    return {}
                return json.loads(text)
        except Exception as e:
            print(f"Error loading memory {memory_path}: {e}")
            return {}

    @staticmethod
    def _save_memory(memory_path: Path, new_data: dict):
        """
        线程/进程安全的保存方法。
        采用 Read-Update-Write 模式，防止覆盖其他进程写入的数据。
        """
        try:
            # 确保父目录存在
            if not memory_path.parent.exists():
                memory_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果文件不存在，先创建一个空 JSON 文件，否则 r+ 模式会报错
            if not memory_path.exists():
                with open(memory_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)

            # === [Modification Start] ===
            # 使用 r+ 模式 (读写)，配合排他锁
            with open(memory_path, "r+", encoding="utf-8") as f:
                if fcntl:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX) # 加排他锁
                
                try:
                    # 1. 读取现有内容
                    content = f.read()
                    existing_data = {}
                    if content.strip():
                        try:
                            existing_data = json.loads(content)
                        except json.JSONDecodeError:
                            existing_data = {}
                    
                    # 2. 合并数据 (将新数据合并到磁盘上的旧数据中)
                    # 注意：这里假设 utils.deep_update 会直接修改第一个参数
                    deep_update(existing_data, new_data)
                    
                    # 3. 回到文件开头
                    f.seek(0)
                    
                    # 4. 截断文件 (如果新内容比旧内容短，这一步很重要)
                    f.truncate()
                    
                    # 5. 写入合并后的数据
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
                    
                finally:
                    if fcntl:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN) # 释放锁
            # === [Modification End] ===
            
        except Exception as e:
            print(f"Failed to save memory to {memory_path}: {e}")
            traceback.print_exc()

    def update_system_prompt(self):
        if self.use_memory:
            memory = sys_memory_prompt_template.format(
                methodology=self.metho_guide_str,
                guidance=self.app_guide_str
            )
        else:
            memory = sys_memory_prompt_template.format(
                methodology="",
                guidance="",
            )
            self.logger.log_task("Pass the memory load step", subtitle="WARNING···", title="use_memory set to False")

        system_prompt = self.sys_prompt_template.format(
            memory=memory,
            tools=self.tool_schema_texts
        )
        if not self.history or self.history[0]["role"] != "system":
            self.history.insert(0, create_message("system", system_prompt))
        else:
            self.history[0] = create_message("system", system_prompt)

    def add_turn(self, user_message: dict, assistant_message: dict):
        self.history.extend([user_message, assistant_message])

    def add_traj(self, trajectory: List[dict]):
        self.history.extend(trajectory)

    def rm_traj_by_length(self, length: int, offset: int = 0):
        if length > 0:
            if offset == 0:
                self.history = self.history[:-length]
            else:
                self.history = self.history[:-(offset + length)] + self.history[-offset:]

    def add_message(self, role: str, content: str):
        self.history.append(create_message(role, content))

    def get_history(self) -> List[dict]:
        return self.history

    @staticmethod
    def trim_traj(
            traj: list,
            preserve_last: int = 0,
            axtree: bool = True,
            state: bool = True,
            python: bool = True,
    ):
        if not isinstance(traj, list) or len(traj) < 2:
            return

        skip = preserve_last * 2
        start = len(traj) - 1 - skip
        if start < 1:
            return

        i = start
        while i >= 1:
            msg_a = traj[i]
            msg_u = traj[i - 1]
            # ... (原有 trim_traj 逻辑保持不变)
            text_u = msg_u["content"][0]["text"]
            if axtree: text_u = remove_accessibility_tree_in_the_history(text_u)
            if state: text_u = remove_browser_state_in_the_history(text_u)
            msg_u["content"][0]["text"] = text_u

            text_a = msg_a["content"][0]["text"]
            if python: text_a = remove_python_code_in_the_history(text_a)
            msg_a["content"][0]["text"] = text_a

            i -= 2

    def update_and_save_app_memory(self, new_conclusion: dict):
        self.logger.log_task(str(new_conclusion), subtitle="UPDATING······", title="Update App Memory")
        # 更新内存中的数据
        deep_update(self.application_enhance_dict, new_conclusion)
        self.app_guide_str = dict_to_outline_str(self.application_enhance_dict)
        # 保存到磁盘（使用修改后的原子保存方法）
        self._save_memory(self.memory_dir / "procedural_memory.json", self.application_enhance_dict)

    def save_all_memory_to_disk(self):
        self._save_memory(self.memory_dir / "tool_memory.json", self.tool_enhance_dict)
        self._save_memory(self.memory_dir / "procedural_memory.json", self.application_enhance_dict)
        self._save_memory(self.memory_dir / "strategic_memory.json", self.methodology_enhance_dict)

    def save_run_artifacts(self, monitor: Monitor):
        output_dir = self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        history_output_path = output_dir / "history.txt"
        history_str = pretty_print_trajectory(self.history, show_full_content=True, print_to_terminal=False)
        
        # === [Modification Start] ===
        # 1. History 使用 "a" (append) 模式，防止覆盖
        with history_output_path.open("a", encoding="utf-8") as f: # 改为 'a'
            if fcntl:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write("\n" + "="*20 + " NEW RUN " + "="*20 + "\n") # 添加分隔符
                    f.write(history_str)
                    f.write("\n")
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            else:
                f.write("\n" + "="*20 + " NEW RUN " + "="*20 + "\n")
                f.write(history_str)
        # === [Modification End] ===

        overall_state_output_path = output_dir / "overall_state.json"
        # 2. State 使用 _save_memory 相同的逻辑 (Read-Update-Write)
        current_state = {
            "monitor_state": asdict(monitor),
            "enhance_dicts": {
                "tool_enhance_dict": self.tool_enhance_dict,
                "application_enhance_dict": self.application_enhance_dict,
                "methodology_enhance_dict": self.methodology_enhance_dict
            }
        }
        # 这里复用 _save_memory 的逻辑来保存 state，或者直接实现一遍
        self._save_memory(overall_state_output_path, current_state)

        # 3. Num calls 也可以考虑追加或更新，这里演示追加
        with open(output_dir / "num_calls.txt", "a", encoding="utf-8") as f:
            if fcntl:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(str({
                        "num_calls": LLM.NUM_CALLS,
                        "prompt_tokens": LLM.PROMPT_TOKENS,
                        "completion_tokens": LLM.COMPLETION_TOKENS,
                        "max_tokens": LLM.MAX_TOKENS
                    }) + "\n")
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            else:
                f.write(str({...}) + "\n")