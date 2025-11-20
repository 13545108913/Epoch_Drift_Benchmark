import json
import requests
import time
import os

# --- 配置 ---
INPUT_FILE = 'gitlab_tasks_processed.json'
BASE_URL = 'http://localhost:8080'  # 替换 __GITLAB__ 的目标地址
PLACEHOLDER = '__GITLAB__'
REQUEST_TIMEOUT = 5  # 每次请求的超时时间（秒）

NOT_FOUND_PHRASES = [
    "404 page not found",
    "page not found",
    "404 not found",
    "couldn't find page",
    "the page you're looking for could not be found",
    "sign in", # 检查是否被重定向到了登录页
    "you need to sign in"
]
# ---

def load_session_from_storage_state(storage_path):
    """
    从 storage_state.json 文件加载 cookies 并创建一个 requests.Session。
    """
    print(f"\n--- 正在从 {storage_path} 加载新的登录会话... ---")
    
    if not os.path.exists(storage_path):
        print(f"  [详细错误] 找不到 'storage_state' 文件: {storage_path}")
        print(f"  [详细错误] 请确保路径相对于您运行脚本的位置是正确的。")
        return None

    try:
        with open(storage_path, 'r', encoding='utf-8') as f:
            storage_data = json.load(f)
        
        cookies_list = storage_data.get('cookies')
        if not cookies_list:
            print(f"  [详细错误] {storage_path} 中未找到 'cookies' 键。")
            return None
        
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
        
        session = requests.Session()
        session.cookies.update(cookie_dict)
        
        print(f"  成功加载 {len(cookie_dict)} 个 cookies。会话已认证。")
        return session
        
    except json.JSONDecodeError as e:
        print(f"  [详细错误] 无法解析 {storage_path}。它不是一个有效的 JSON。")
        print(f"  [详细错误] JSON 错误: {e}")
        return None
    except Exception as e:
        print(f"  [详细错误] 加载 cookies 时发生未知错误: {e}")
        return None

def check_url_accessibility(url, session):
    """
    使用一个已认证的 session (带 cookies) 检查 URL。
    返回 (状态, 详细消息)
    """
    if not url:
        return ("SKIP", "URL为空")
    
    if not session:
        return ("ERROR", "跳过 - 登录会话 (Session) 无效")

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        
        if response.status_code < 400:
            page_content = response.text.lower()
            
            found_error_phrase = False
            for phrase in NOT_FOUND_PHRASES:
                if phrase in page_content:
                    found_error_phrase = True
                    # 检查是否因为会话失效而被踢到登录页
                    if "sign in" in phrase or "you need to sign in" in phrase:
                        return ("ERROR", f"被重定向到登录页 (Status: {response.status_code}) - Cookie 可能已失效")
                    break
            
            if found_error_phrase:
                return ("ERROR", f"内容错误 (Status: {response.status_code} 但页面包含 'Page Not Found' 关键字)")
            else:
                return ("OK", f"可访问 (Status: {response.status_code})")
        
        elif response.status_code == 404:
             return ("ERROR", f"不可访问 (Status: 404 Not Found)")
        elif response.status_code == 403:
             return ("ERROR", f"不可访问 (Status: 403 Forbidden) - 无权限")
        else:
            return ("ERROR", f"不可访问 (Status: {response.status_code})")

    except requests.exceptions.ConnectionError as e:
        return ("ERROR", f"连接失败 - 无法连接到 {BASE_URL}。请确保服务正在运行。 (详情: {e})")
    except requests.exceptions.Timeout:
        return ("ERROR", f"请求超时 (超过 {REQUEST_TIMEOUT} 秒)")
    except requests.exceptions.RequestException as e:
        # **这里提供更详细的错误信息**
        return ("ERROR", f"发生未知的请求错误: {e}")

def main():
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        print(f"[致命错误] 未找到输入文件 '{INPUT_FILE}'。")
        print("请确保 'gitlab_tasks_processed.json' 文件在当前目录中。")
        return
    except json.JSONDecodeError as e:
        print(f"[致命错误] 文件 '{INPUT_FILE}' 格式不正确，无法解析。")
        print(f"[致命错误] JSON 错误: {e}")
        return
    
    print(f"--- 网址可访问性检测开始 (使用已认证的Session) ---")
    print(f"共 {len(tasks)} 个任务。")
    print(f"占位符 '{PLACEHOLDER}' 将被替换为 '{BASE_URL}'\n")

    error_list = [] # 用于存储所有错误的详细信息
    total_checks = 0
    
    current_storage_path = None
    current_session = None

    for task in tasks:
        task_id = task.get('task_id')
        print(f"--- [任务 {task_id}] ---")
        
        task_storage_path = task.get('storage_state')
        session_valid = True

        # 1. 检查是否需要加载或更新 Session
        if not task_storage_path:
            print(f"  [警告] 任务 {task_id} 没有 'storage_state'，无法进行认证检测。")
            current_session = None 
            session_valid = False
        elif task_storage_path != current_storage_path:
            # 这是一个新的 storage_state 路径，加载新 session
            current_storage_path = task_storage_path
            current_session = load_session_from_storage_state(current_storage_path)
            if not current_session:
                print(f"  [错误] 无法加载 session。将跳过此任务及后续使用相同 state 的任务。")
                session_valid = False
        elif not current_session:
             # storage_state 路径相同，但上次加载失败了
             session_valid = False

        # 准备 URL 列表
        urls_to_check = []
        start_url = task.get('start_url')
        if start_url and isinstance(start_url, str):
            urls_to_check.append(("start_url", start_url.replace(PLACEHOLDER, BASE_URL)))
        else:
            print("  start_url: 未提供或格式不正确")

        eval_dict = task.get('eval', {})
        ref_url = eval_dict.get('reference_url')
        if ref_url and isinstance(ref_url, str):
            urls_to_check.append(("reference_url", ref_url.replace(PLACEHOLDER, BASE_URL)))
        else:
            print("  reference_url: 为空或未提供，已跳过")
        
        # 2. 检查 URL
        if not session_valid and urls_to_check:
            print("  [跳过] 由于 'storage_state' 加载失败或缺失，跳过 URL 检测。")
            # 记录错误
            for url_type, full_url in urls_to_check:
                error_list.append({
                    "task_id": task_id,
                    "url_type": url_type,
                    "url": full_url,
                    "error": "登录会话 (Session) 无效"
                })
            continue # 跳到下一个任务

        for url_type, full_url in urls_to_check:
            total_checks += 1
            status, message = check_url_accessibility(full_url, current_session)
            
            print(f"  {url_type}: {full_url}")
            print(f"  结果: [{status}] {message}\n")
            
            if status == "ERROR":
                # 记录错误详情
                error_list.append({
                    "task_id": task_id,
                    "url_type": url_type,
                    "url": full_url,
                    "error": message
                })
            
        time.sleep(0.05) 

    # --- 3. 打印最终的详细错误报告 ---
    print("\n" + "="*40)
    print("--- 详细错误报告 ---")
    print("="*40)
    
    error_id = []
    if not error_list:
        print("太好了！所有 URL 均检测通过。")
    else:
        print(f"检测完成，总共发现 {len(error_list)} 个错误。")
        print("错误列表：\n")
        
        current_task_id = -1
        for err in error_list:
            # 按 Task ID 组合
            if err['task_id'] != current_task_id:
                print(f"\n[任务 ID: {err['task_id']}]")
                current_task_id = err['task_id']
            # 打印该任务下的错误
            print(f"  - URL 类型: {err['url_type']}")
            print(f"  - URL: {err['url']}")
            print(f"  - 错误信息: {err['error']}")
            error_id.append(err['task_id'])

    print("\n--- 总结 ---")
    print(f"总共检测了 {total_checks} 个 URL。")
    print(f"总共发现 {len(error_list)} 个错误。")
    print(error_id)

if __name__ == "__main__":
    main()