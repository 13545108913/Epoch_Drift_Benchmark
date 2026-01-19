import os
import json
import time
import tiktoken
from filelock import FileLock

class UsageRecorder:
    def __init__(self, log_file="llm_usage_stats.jsonl", model_name="gpt-4"):
        self.log_file = log_file
        self.lock_file = f"{log_file}.lock"
        self.model_name = model_name
        
        # 初始化 tokenizer (根据你的实际模型选择编码，这里以 cl100k_base 为例)

        self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def record(self, prompt: str, completion: str, caller_method: str = "unknown"):
        """
        记录一次调用信息
        """
        input_tokens = self.count_tokens(prompt)
        output_tokens = self.count_tokens(completion)
        total_tokens = input_tokens + output_tokens
        
        record_data = {
            "timestamp": time.time(),
            "readable_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "caller": caller_method,
            "model": self.model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record_data, ensure_ascii=False) + "\n")