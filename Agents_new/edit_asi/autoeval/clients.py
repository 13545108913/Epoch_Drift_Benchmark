import os
import base64
import io
import openai
import numpy as np
from PIL import Image
from typing import Union, Optional
from openai import OpenAI
from openai.types.chat import ChatCompletion

# --- Client Initialization (Modified) ---
MY_API_KEY = os.getenv("my_api_key")
MY_BASE_URL = os.getenv("my_base_url")
MY_MODEL = os.getenv("my_model")

client = OpenAI(
    api_key=MY_API_KEY,
    base_url=MY_BASE_URL
)

class LM_Client:
    """Client for text-only language models."""
    def __init__(self, model_name: str = "gpt-3.5-turbo") -> None:
        self.model_name = model_name

    def chat(self, messages, json_mode: bool = False) -> tuple[str, ChatCompletion]:
        """Generic chat completion request."""
        chat_completion = client.chat.completions.create(
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
        """Simplified chat with a single user message."""
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})
        messages.append({"role": "user", "content": text})
        return self.chat(messages, json_mode=json_mode)

class GPT4V_Client:
    """Client for multimodal (vision) language models."""
    def __init__(self, model_name: str = "gpt-4o", max_tokens: int = 1500): # Increased default tokens
        self.model_name = model_name
        self.max_tokens = max_tokens

    def encode_image(self, image: Union[str, Image.Image, np.ndarray]) -> str:
        """
        Encodes an image from a file path, PIL Image, or Numpy array to a base64 string.
        (This method has been fixed to handle different image types).
        """
        if isinstance(image, str): # Image is a file path
            with open(image, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        elif isinstance(image, Image.Image): # Image is a PIL object
            buffered = io.BytesIO()
            image_format = image.format if image.format else 'PNG'
            image.save(buffered, format=image_format)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        elif isinstance(image, np.ndarray): # Image is a Numpy array
            pil_img = Image.fromarray(image)
            buffered = io.BytesIO()
            pil_img.save(buffered, format='PNG')
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        else:
            raise TypeError("Unsupported image type. Use file path (str), PIL.Image, or np.ndarray.")


    def one_step_chat(
        self, text: str, image: Union[str, Image.Image, np.ndarray],
        system_msg: Optional[str] = None,
    ) -> tuple[str, ChatCompletion]:
        """Performs a chat completion with a single text and image message."""
        base64_str = self.encode_image(image)
        messages = []
        if system_msg is not None:
            messages.append({"role": "system", "content": system_msg})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_str}"}},
            ],
        })

        response = client.chat.completions.create(
            model=MY_MODEL,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0,
        )
        return response.choices[0].message.content, response

# --- CLIENT DICTIONARY (Updated) ---
# Added the new gpt-5-mini model, mapping it to the vision client.
CLIENT_DICT = {
    "gpt-3.5-turbo": LM_Client,
    "gpt-4": LM_Client,
    "gpt-4o": GPT4V_Client,
    "gpt-4o-2024-05-13": GPT4V_Client,
    "gpt-5-mini-2025-08-07": GPT4V_Client,
    "claude-haiku-4-5-20251001": GPT4V_Client,
}
