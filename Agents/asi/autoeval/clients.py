import os
import base64
import openai
import numpy as np
from PIL import Image
from typing import Union, Optional
from openai import OpenAI, ChatCompletion

# --- 默认的 OpenAI 客户端 ---
# openai.api_key = os.environ.get("OPENAI_API_KEY", "")
# openai.organization = os.environ.get("OPENAI_ORGANIZATION", "")
# client = OpenAI()


# class LM_Client:
#     def __init__(self, model_name: str = "gpt-3.5-turbo") -> None:
#         self.model_name = model_name

#     def chat(self, messages, json_mode: bool = False) -> tuple[str, ChatCompletion]:
#         """
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user", "content": "hi"},
#         ])
#         """
#         chat_completion = client.chat.completions.create(
#             model=self.model_name,
#             messages=messages,
#             response_format={"type": "json_object"} if json_mode else None,
#             temperature=0,
#         )
#         response = chat_completion.choices[0].message.content
#         return response, chat_completion

#     def one_step_chat(
#         self, text, system_msg: str = None, json_mode=False
#     ) -> tuple[str, ChatCompletion]:
#         messages = []
#         if system_msg is not None:
#             messages.append({"role": "system", "content": system_msg})
#         messages.append({"role": "user", "content": text})
#         return self.chat(messages, json_mode=json_mode)


# class GPT4V_Client:
#     def __init__(self, model_name: str = "gpt-4o", max_tokens: int = 512):
#         self.model_name = model_name
#         self.max_tokens = max_tokens

#     def encode_image(self, path: str):
#         with open(path, 'rb') as f:
#             return base64.b64encode(f.read()).decode('utf-8')
                         
#     def one_step_chat(
#         self, text, image: Union[Image.Image, np.ndarray], 
#         system_msg: Optional[str] = None,
#     ) -> tuple[str, ChatCompletion]:
#         # 注意：这里的 image: Union[Image.Image, np.ndarray] 
#         # 与 encode_image(path: str) 的类型不匹配。
#         # 我将保持原样，因为你没有要求我修复它。
#         jpg_base664_str = self.encode_image(image) 
#         messages = []
#         if system_msg is not None:
#             messages.append({"role": "system", "content": system_msg})
#         messages += [{
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": text},
#                     {"type": "image_url",
#                     "image_url": {"url": f"data:image/jpeg;base64,{jpg_base664_str}"},},
#                 ],
#         }]
#         response = client.chat.completions.create(
#             model=self.model_name,
#             messages=messages,
#             max_tokens=self.max_tokens,
#             temperature=0,
#         )
#         return response.choices[0].message.content, response


# <--- 新增的 Deepseek_Client --->
class Deepseek_Client:
    def __init__(self, model_name: str = "deepseek-chat") -> None:
        self.model_name = model_name
        
        # **重要提示**：
        # 出于安全考虑，硬编码 API 密钥（sk-41fa...）非常不安全。
        # 这里的代码会优先尝试从环境变量 DEEPSEEK_API_KEY 中获取密钥。
        # 如果找不到，它将使用你提供的硬编码密钥作为后备。
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-41fae6597fd14d6fa2c5c4068c0e5760")
        self.base_url = "https://api.deepseek.com"
        
        # 为 DeepSeek 创建一个专用的 OpenAI 客户端实例
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def chat(self, messages, json_mode: bool = False) -> tuple[str, ChatCompletion]:
        """
        使用 self.client（DeepSeek 客户端）而不是全局 client。
        """
        chat_completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"} if json_mode else None,
            temperature=0,
        )
        response = chat_completion.choices[0].message.content
        return response, chat_completion

    def one_step_chat(
        self, text, system_msg: str = None, json_mode=False
    ) -> tuple[str, ChatCompletion]:
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": text})
        return self.chat(messages, json_mode=json_mode)
# <--- Deepseek_Client 结束 --->


# CLIENT_DICT = {
#     "gpt-3.5-turbo": LM_Client,
#     "gpt-4": LM_Client,
#     "gpt-4o": GPT4V_Client,
#     "gpt-4o-2024-05-13": GPT4V_Client,
#     "deepseek-chat": Deepseek_Client,  # <--- 在这里添加了 DeepSeek
# }

CLIENT_DICT = {
    "deepseek-chat": Deepseek_Client,  # <--- 在这里添加了 DeepSeek
}