import json
import requests
import time
import os
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# 尝试导入 BeautifulSoup
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[错误] 缺少必要库 'beautifulsoup4'。")
    print("请运行: pip install beautifulsoup4")
    exit(1)

# --- 默认配置 ---
DEFAULT_INPUT_FILE = 'admin_tasks_processed_v1.json'
DEFAULT_BASE_URL = 'http://172.26.116.102:8081'
PLACEHOLDER = '__GITLAB__'
REQUEST_TIMEOUT = 10  # 增加超时时间以应对大页面
MAX_WORKERS = 10     

NOT_FOUND_PHRASES = [
    "404 page not found",
    "page not found",
    "404 not found",
    "couldn't find page",
    "the page you're looking for could not be found",
    "you need to sign in"
]

# 全局缓存
session_cache = {}

def load_session_from_storage_state(storage_path):
    """加载并缓存 Session"""
    if not storage_path:
        return None
    if storage_path in session_cache:
        return session_cache[storage_path]

    if not os.path.exists(storage_path):
        # 尝试相对于当前脚本的路径
        rel_path = os.path.join(os.path.dirname(__file__), storage_path)
        if os.path.exists(rel_path):
            storage_path = rel_path
        else:
            print(f"[警告] 找不到认证文件: {storage_path}")
            session_cache[storage_path] = None
            return None

    try:
        with open(storage_path, 'r', encoding='utf-8') as f:
            storage_data = json.load(f)
        
        cookies_list = storage_data.get('cookies')
        if not cookies_list:
            session_cache[storage_path] = None
            return None
        
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies_list}
        session = requests.Session()
        session.cookies.update(cookie_dict)
        session_cache[storage_path] = session
        return session
    except Exception as e:
        print(f"[异常] 加载 {storage_path} 失败: {e}")
        session_cache[storage_path] = None
        return None

def extract_css_selector(locator_js):
    """
    从 JS locator 字符串中提取 CSS 选择器。
    支持:
    - document.querySelector('selector')
    - document.querySelectorAll("selector")
    """
    if not locator_js:
        return None
    
    # 匹配 document.querySelector(All)? ('或") (内容) ('或")
    # 使用非贪婪匹配 (.*?)
    pattern = r"document\.querySelectorAll?\s*\(\s*['\"](.*?)['\"]\s*\)"
    match = re.search(pattern, locator_js)
    if match:
        return match.group(1)
    return None

def check_single_url(task_id, url_type, url, storage_path, locator=None):
    """
    检测单个 URL 的可访问性，如果提供了 locator，则额外检测其在页面中的唯一性。
    """
    result = {
        "task_id": task_id,
        "url_type": url_type,
        "url": url,
        "locator": locator,
        "status": "UNKNOWN",
        "message": "",
        "is_error": False
    }

    if not url:
        result["status"] = "SKIP"
        result["message"] = "URL为空"
        return result

    session = load_session_from_storage_state(storage_path)
    if not session:
        result["status"] = "SESSION_ERR"
        result["message"] = "登录会话无效或文件缺失"
        result["is_error"] = True
        return result

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        
        # --- 1. HTTP 状态检测 ---
        if response.status_code >= 400:
            result["status"] = f"HTTP_{response.status_code}"
            result["message"] = f"不可访问 (Status: {response.status_code})"
            result["is_error"] = True
            return result

        # --- 2. 页面内容关键字检测 ---
        page_content_lower = response.text.lower()
        for phrase in NOT_FOUND_PHRASES:
            if phrase in page_content_lower:
                if "sign in" in phrase:
                    result["status"] = "AUTH_FAIL"
                    result["message"] = f"重定向到登录页 (可能Cookie失效)"
                else:
                    result["status"] = "CONTENT_ERR"
                    result["message"] = f"页面包含错误提示: '{phrase}'"
                result["is_error"] = True
                return result
        
        # 基础 URL 检查通过
        result["status"] = "OK"
        result["message"] = f"可访问 (Code: {response.status_code})"

        """ # --- 3. Locator 唯一性检测 (如果存在) ---
        if locator:
            # 跳过 func: 类型的 locator (需要 Python eval，静态脚本不支持)
            if locator.strip().startswith("func:"):
                result["message"] += " | [Locator跳过] 暂不支持检测 'func:' 类型"
                return result

            css_selector = extract_css_selector(locator)
            
            if css_selector:
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    elements = soup.select(css_selector)
                    count = len(elements)
                    
                    if count == 0:
                        result["status"] = "LOCATOR_NOT_FOUND"
                        result["message"] += f" | [Locator错误] 未找到元素 (0 matches): {css_selector}"
                        result["is_error"] = True
                    elif count == 1:
                        result["message"] += f" | [Locator正常] 唯一定位成功"
                    else:
                        result["status"] = "LOCATOR_NOT_UNIQUE"
                        result["message"] += f" | [Locator错误] 定位不唯一 (发现 {count} 个): {css_selector}"
                        result["is_error"] = True
                except Exception as e:
                    result["status"] = "LOCATOR_PARSE_ERR"
                    result["message"] += f" | [Locator异常] BeautifulSoup解析失败: {e}"
                    result["is_error"] = True
            else:
                # 无法解析 CSS 选择器 (可能是复杂的 JS 逻辑)
                # 这种情况下标记为警告而不是错误，因为可能是 BeautifulSoup 无法处理但 Playwright 可以处理的 JS
                result["status"] = "LOCATOR_UNKNOWN_FMT"
                result["message"] += f" | [Locator警告] 无法提取CSS选择器，无法静态检测: {locator[:30]}..."
                # 视需求决定是否算作 Error，这里暂时算作 Warning (is_error=False) """

    except requests.exceptions.RequestException as e:
        result["status"] = "REQ_ERR"
        result["message"] = f"请求异常: {str(e)}"
        result["is_error"] = True
    except Exception as e:
        result["status"] = "SYS_ERR"
        result["message"] = f"系统错误: {str(e)}"
        result["is_error"] = True

    return result

def main():
    parser = argparse.ArgumentParser(description='GitLab URL & Locator 检测工具')
    parser.add_argument('-f', '--file', default=DEFAULT_INPUT_FILE, help='JSON 任务文件')
    parser.add_argument('-u', '--url', default=DEFAULT_BASE_URL, help='GitLab Base URL')
    parser.add_argument('-w', '--workers', type=int, default=MAX_WORKERS, help='并发数')
    args = parser.parse_args()

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except Exception as e:
        print(f"[致命错误] 读取文件失败: {e}")
        return

    print(f"--- 开始检测: {len(tasks)} 个任务 ---")
    print(f"目标 Base URL: {args.url}")
    
    futures = []
    error_results = []
    total_checks = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for task in tasks:
            task_id = task.get('task_id')
            storage_path = task.get('storage_state')

            # 收集需要检测的项目 (type, url, locator)
            items_to_check = []

            # 1. Start URL
            if task.get('start_url'):
                u = task['start_url'].replace(PLACEHOLDER, args.url)
                items_to_check.append(("start_url", u, None))

            # 2. Reference URL (用于后续 'last' 引用)
            ref_url_final = None
            ref_url_raw = task.get('eval', {}).get('reference_url')
            if ref_url_raw:
                ref_url_final = ref_url_raw.replace(PLACEHOLDER, args.url)
                items_to_check.append(("reference_url", ref_url_final, None))

            # 3. Program HTML
            prog_html = task.get('eval', {}).get('program_html', [])
            if prog_html:
                for idx, item in enumerate(prog_html):
                    p_url = item.get('url')
                    p_locator = item.get('locator')
                    target_url = None

                    # 处理 URL
                    if p_url == "last":
                        if ref_url_final:
                            target_url = ref_url_final
                        else:
                            # 错误: 引用了 last 但没有 reference_url
                            err = {
                                "task_id": task_id,
                                "url_type": f"program_html[{idx}]",
                                "url": "last",
                                "status": "CFG_ERR",
                                "message": "URL设为 'last' 但 reference_url 为空",
                                "is_error": True
                            }
                            error_results.append(err)
                            print(f"[Task {task_id}] Config Error: {err['message']}")
                            continue
                    elif p_url and p_url.startswith("func:"):
                        # 尝试简单处理 func，虽然 requests 无法执行代码，
                        # 但如果它只是简单的字符串替换，我们可以尝试解析
                        # 例如: func: "http://..." + "__page__" (这种情况很难静态处理)
                        # 这里我们只做记录，暂不检测 func 类型的 URL
                        pass 
                    elif p_url:
                        target_url = p_url.replace(PLACEHOLDER, args.url)

                    if target_url:
                        items_to_check.append((f"program_html[{idx}]", target_url, p_locator))

            # 提交任务
            for utype, u, loc in items_to_check:
                total_checks += 1
                futures.append(executor.submit(
                    check_single_url, task_id, utype, u, storage_path, loc
                ))

        # 处理结果
        print(f"正在并发检测 {total_checks} 个目标...\n")
        done_count = 0
        for future in as_completed(futures):
            res = future.result()
            done_count += 1
            if done_count % 20 == 0:
                print(f"进度: {done_count}/{total_checks}...")

            if res["is_error"]:
                print(f"[Task {res['task_id']}] {res['url_type']} | {res['status']} | {res['message']}")
                error_results.append(res)

    # 报告
    print("\n" + "="*40)
    print(f"检测结束。总计: {total_checks}, 失败: {len(error_results)}")
    if error_results:
        out_file = "check_report_v1.json"
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(error_results, f, indent=2, ensure_ascii=False)
        print(f"错误详情已写入 {out_file}")
        
        # 打印一下 Locator 相关的特定错误统计
        locator_errs = [e for e in error_results if "LOCATOR" in e.get("status", "")]
        if locator_errs:
            print(f"其中 Locator 相关错误: {len(locator_errs)} 个")
    else:
        print("所有检测通过！")

if __name__ == "__main__":
    main()