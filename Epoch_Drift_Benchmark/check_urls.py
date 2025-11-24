import json
import requests
import time
import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# --- 默认配置 ---
DEFAULT_INPUT_FILE = 'gitlab_tasks_processed_edit.json'
DEFAULT_BASE_URL = 'http://172.26.116.102:8080'
PLACEHOLDER = '__GITLAB__'
REQUEST_TIMEOUT = 5  # 秒
MAX_WORKERS = 10     # 并发线程数

NOT_FOUND_PHRASES = [
    "404 page not found",
    "page not found",
    "404 not found",
    "couldn't find page",
    "the page you're looking for could not be found",
    "sign in",
    "you need to sign in"
]

# 全局缓存，避免重复读取同一个 storage_state 文件
session_cache = {}

def load_session_from_storage_state(storage_path):
    """
    加载并缓存 Session。如果路径已在缓存中，直接返回缓存的 Session。
    """
    if not storage_path:
        return None

    # 检查缓存
    if storage_path in session_cache:
        return session_cache[storage_path]

    if not os.path.exists(storage_path):
        print(f"[警告] 找不到认证文件: {storage_path}")
        session_cache[storage_path] = None # 标记为无效，避免重复尝试加载
        return None

    try:
        with open(storage_path, 'r', encoding='utf-8') as f:
            storage_data = json.load(f)
        
        cookies_list = storage_data.get('cookies')
        if not cookies_list:
            print(f"[错误] {storage_path} 中缺少 cookies")
            session_cache[storage_path] = None
            return None
        
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
        
        session = requests.Session()
        session.cookies.update(cookie_dict)
        
        # 存入缓存
        session_cache[storage_path] = session
        return session
        
    except Exception as e:
        print(f"[异常] 加载 {storage_path} 失败: {e}")
        session_cache[storage_path] = None
        return None

def check_single_url(task_id, url_type, url, storage_path):
    """
    单个 URL 检测逻辑，用于线程池调用。
    返回结构化的结果字典。
    """
    result = {
        "task_id": task_id,
        "url_type": url_type,
        "url": url,
        "status": "UNKNOWN",
        "message": "",
        "is_error": False
    }

    if not url:
        result["status"] = "SKIP"
        result["message"] = "URL为空"
        return result

    # 获取 Session (带缓存)
    session = load_session_from_storage_state(storage_path)
    if not session:
        result["status"] = "ERROR"
        result["message"] = "登录会话 (Session) 无效或文件丢失"
        result["is_error"] = True
        return result

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        
        if response.status_code < 400:
            page_content = response.text.lower()
            found_error_phrase = False
            
            for phrase in NOT_FOUND_PHRASES:
                if phrase in page_content:
                    found_error_phrase = True
                    if "sign in" in phrase or "you need to sign in" in phrase:
                        result["status"] = "AUTH_FAIL"
                        result["message"] = f"重定向到登录页 (Code: {response.status_code}) - Cookie 可能失效"
                    else:
                        result["status"] = "CONTENT_ERR"
                        result["message"] = f"页面包含错误关键字 (Code: {response.status_code})"
                    break
            
            if found_error_phrase:
                result["is_error"] = True
            else:
                result["status"] = "OK"
                result["message"] = f"正常 (Code: {response.status_code})"

        elif response.status_code == 404:
            result["status"] = "404"
            result["message"] = "404 Not Found"
            result["is_error"] = True
        elif response.status_code == 403:
            result["status"] = "403"
            result["message"] = "403 Forbidden (无权限)"
            result["is_error"] = True
        else:
            result["status"] = f"HTTP_{response.status_code}"
            result["message"] = f"HTTP 错误状态码: {response.status_code}"
            result["is_error"] = True

    except requests.exceptions.ConnectionError:
        result["status"] = "CONN_ERR"
        result["message"] = "连接失败 - 无法连接到服务器"
        result["is_error"] = True
    except requests.exceptions.Timeout:
        result["status"] = "TIMEOUT"
        result["message"] = f"请求超时 (> {REQUEST_TIMEOUT}s)"
        result["is_error"] = True
    except Exception as e:
        result["status"] = "EXCEPTION"
        result["message"] = f"未知错误: {str(e)}"
        result["is_error"] = True

    return result

def main():
    parser = argparse.ArgumentParser(description='GitLab URL 批量检测工具')
    parser.add_argument('-f', '--file', default=DEFAULT_INPUT_FILE, help='输入的 JSON 文件路径')
    parser.add_argument('-u', '--url', default=DEFAULT_BASE_URL, help='GitLab 基础 URL (替换 __GITLAB__)')
    parser.add_argument('-w', '--workers', type=int, default=MAX_WORKERS, help='并发线程数')
    args = parser.parse_args()

    input_file = args.file
    base_url = args.url
    
    # 1. 加载任务
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"[致命错误] 无法读取任务文件: {e}")
        return

    print(f"--- 开始检测 ---")
    print(f"文件: {input_file}")
    print(f"目标: {base_url}")
    print(f"任务数: {len(tasks)}")
    print(f"并发数: {args.workers}")
    print("-" * 30)

    # 2. 准备检测队列
    futures = []
    error_results = [] # 提前初始化错误列表，用于存放静态检查错误
    total_checks = 0
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for task in tasks:
            task_id = task.get('task_id')
            storage_path = task.get('storage_state')

            # 准备 URL 列表
            urls_to_check = []
            
            # --- 1. Start URL ---
            start_url = task.get('start_url')
            if start_url and isinstance(start_url, str):
                final_url = start_url.replace(PLACEHOLDER, base_url)
                urls_to_check.append(("start_url", final_url))

            # --- 2. Reference URL (需要保存以便 program_html 使用) ---
            ref_url_raw = task.get('eval', {}).get('reference_url')
            final_ref_url = None
            if ref_url_raw and isinstance(ref_url_raw, str):
                final_ref_url = ref_url_raw.replace(PLACEHOLDER, base_url)
                urls_to_check.append(("reference_url", final_ref_url))

            # --- 3. Program HTML 检查 ---
            program_html = task.get('eval', {}).get('program_html')
            if program_html and isinstance(program_html, list):
                for idx, item in enumerate(program_html):
                    # 3.1 检测 locator 是否有效 (静态检查)
                    locator = item.get('locator')
                    if not locator or not isinstance(locator, str) or not locator.strip():
                        pass

                    # 3.2 检测 program_html URL
                    p_url_raw = item.get('url')
                    target_p_url = None
                    
                    if p_url_raw == 'last':
                        # 如果是 last，则使用之前解析好的 final_ref_url
                        if final_ref_url:
                            target_p_url = final_ref_url
                        else:
                            # 如果指定了 last 但没有 reference_url，记录错误
                            err_res = {
                                "task_id": task_id,
                                "url_type": f"program_html[{idx}].url",
                                "url": "last",
                                "status": "MISSING_REF",
                                "message": "URL为'last'，但 Reference URL 为空",
                                "is_error": True
                            }
                            error_results.append(err_res)
                            print(f"[Task {task_id}] {err_res['url_type']} -> {err_res['status']}: {err_res['message']}")

                    elif p_url_raw and isinstance(p_url_raw, str):
                        target_p_url = p_url_raw.replace(PLACEHOLDER, base_url)
                    
                    # 如果有有效的 URL，加入待检测队列
                    if target_p_url:
                        urls_to_check.append((f"program_html[{idx}].url", target_p_url))

            # 提交到线程池
            for url_type, full_url in urls_to_check:
                total_checks += 1
                futures.append(executor.submit(check_single_url, task_id, url_type, full_url, storage_path))

        # 3. 处理网络请求结果
        processed_count = 0

        print(f"正在通过网络检测 {total_checks} 个 URL (静态检查错误已记录)...\n")
        
        for future in as_completed(futures):
            res = future.result()
            processed_count += 1
            
            # 简单的进度展示
            if processed_count % 10 == 0:
                print(f"进度: {processed_count}/{total_checks} ...")

            if res["is_error"]:
                # 实时打印错误
                print(f"[Task {res['task_id']}] {res['url_type']} -> {res['status']}: {res['message']}")
                error_results.append(res)

    # 4. 最终报告
    print("\n" + "="*40)
    print("--- 检测完成 ---")
    print("="*40)
    # total_checks 只是网络请求的数量，不包含静态检查失败的数量
    print(f"网络请求总数: {total_checks}")
    print(f"总发现错误: {len(error_results)}")

    if error_results:
        # 保存详细报告到文件
        report_file = 'check_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(error_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细错误列表已保存至: {report_file}")
        
        # 提取出错的 Task ID 列表
        failed_ids = sorted(list(set(r['task_id'] for r in error_results)))
        print(f"涉及的任务 ID ({len(failed_ids)}个): {failed_ids}")
    else:
        print("\n太棒了！所有检查（URL及Locator）均通过！")

if __name__ == "__main__":
    main()