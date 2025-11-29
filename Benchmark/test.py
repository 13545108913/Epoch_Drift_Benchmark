import requests
import json

# API配置
DEEPSEEK_API_KEY = "sk-41fae6597fd14d6fa2c5c4068c0e5760"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

class DeepSeekClient:
    def __init__(self, api_key, base_url, model):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def chat_completion(self, messages, temperature=0.7, max_tokens=2048, stream=False):
        """
        调用DeepSeek聊天补全API
        
        Args:
            messages: 对话消息列表，格式如 [{"role": "user", "content": "你好"}]
            temperature: 生成文本的随机性，0-1之间
            max_tokens: 最大生成长度
            stream: 是否使用流式输出
        
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API请求错误: {e}")
            return None
    
    def simple_chat(self, prompt):
        """
        简化版的聊天方法
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat_completion(messages)

# 使用示例
def main():
    # 初始化客户端
    client = DeepSeekClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    
    # 示例1: 简单对话
    print("=== 简单对话示例 ===")
    response = client.simple_chat("你好，请介绍一下你自己")
    if response and 'choices' in response:
        answer = response['choices'][0]['message']['content']
        print(f"AI: {answer}")
    
    print("\n" + "="*50 + "\n")
    
    # 示例2: 多轮对话
    print("=== 多轮对话示例 ===")
    conversation = [
        {"role": "user", "content": "Python是什么？"},
        {"role": "assistant", "content": "Python是一种高级编程语言，以简洁易读著称。"},
        {"role": "user", "content": "它有哪些主要应用领域？"}
    ]
    
    response = client.chat_completion(conversation)
    if response and 'choices' in response:
        answer = response['choices'][0]['message']['content']
        print(f"AI: {answer}")
    
    print("\n" + "="*50 + "\n")
    
    # 示例3: 获取详细的API响应信息
    print("=== 完整响应信息 ===")
    response = client.simple_chat("今天的天气怎么样？")
    if response:
        print("完整响应:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

# 交互式聊天函数
def interactive_chat():
    """交互式聊天模式"""
    client = DeepSeekClient(DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)
    conversation_history = []
    
    print("=== DeepSeek 交互式聊天 ===")
    print("输入 'quit' 或 '退出' 结束对话")
    print("-" * 40)
    
    while True:
        user_input = input("\n你: ").strip()
        
        if user_input.lower() in ['quit', '退出', 'exit']:
            print("对话结束，再见！")
            break
        
        if not user_input:
            continue
        
        # 添加用户消息到对话历史
        conversation_history.append({"role": "user", "content": user_input})
        
        # 调用API
        response = client.chat_completion(conversation_history)
        
        if response and 'choices' in response:
            ai_response = response['choices'][0]['message']['content']
            print(f"\nAI: {ai_response}")
            
            # 添加AI回复到对话历史
            conversation_history.append({"role": "assistant", "content": ai_response})
        else:
            print("\nAI: 抱歉，我暂时无法回应。")

if __name__ == "__main__":
    # 运行示例
    main()
    
    # 启动交互式聊天（取消注释以启用）
    # interactive_chat()