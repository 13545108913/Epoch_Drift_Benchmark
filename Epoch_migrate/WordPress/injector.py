import json
import subprocess
import concurrent.futures
import datetime
import os
import time
from threading import Lock

# =======================================
# 新增: 尝试导入 markdown 库以处理内容格式
# 建议运行: pip install markdown
# =======================================
try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    print("⚠️  Warning: 'markdown' library not found. Falling back to simple text formatting.")
    print("   For best results, install it using: pip install markdown")

# ================= 配置 =================
JSON_FILE = 'diverse_real_world_data.json'
MAX_WORKERS = 5  # 并行线程数，建议 5-10，过高可能导致数据库锁
WP_USER = 'admin' # 对应你初始化时的管理员用户
# =======================================

print_lock = Lock()
success_count = 0
fail_count = 0

def parse_date(date_str):
    """
    将 "Tue, 18 Nov 2025 15:00:00 GMT" 转换为 "2025-11-18 15:00:00"
    """
    try:
        # Python 3.7+ fromisoformat 或者 strptime
        # 针对示例格式: Tue, 18 Nov 2025 15:00:00 GMT
        dt = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        # 如果解析失败，返回当前时间作为兜底
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def process_content(raw_content):
    """
    将 Markdown 或 纯文本 转换为 WordPress 友好的 HTML
    """
    if not raw_content:
        return ""
        
    if HAS_MARKDOWN:
        # 使用 markdown 库转换
        # extensions=['extra'] 支持表格、脚注、代码块等更多 Markdown 特性
        # 这对 Trafilatura 的输出非常有效，对 BS4 的纯文本也能正确处理段落
        return markdown.markdown(raw_content, extensions=['extra'])
    else:
        # 简易兜底：如果没有安装 markdown 库
        # 将双换行视为段落，单换行视为 <br>
        # 这是一个简单的 fallback，效果不如 markdown 库好
        lines = raw_content.split('\n\n')
        # 过滤空行并包裹 <p>
        paragraphs = [f'<p>{line.strip().replace(chr(10), "<br>")}</p>' for line in lines if line.strip()]
        return ''.join(paragraphs)

def import_single_article(article):
    """
    导入单篇文章到 WordPress
    """
    global success_count, fail_count
    
    # 1. 准备基础字段
    title = article.get('title', 'Untitled')
    raw_content = article.get('content', '')
    
    # 处理内容格式: 转换为 HTML
    content = process_content(raw_content)
    
    date_gmt = parse_date(article.get('published_date', ''))
    
    # 2. 准备 Meta Data (自定义字段)
    # 我们将额外的字段存入 post_meta，方便后续检索
    meta_input = {
        'original_id': article.get('id'),
        'source_url': article.get('source_url'),
        'crawl_timestamp': article.get('crawl_timestamp'),
        'content_hash': article.get('content_hash'),
        'source_feed': article.get('source_feed')
    }
    
    # 将 meta dict 转换为 JSON 字符串传递给 WP-CLI
    # 注意：WP-CLI 的 --meta_input 接受 JSON 格式
    meta_json = json.dumps(meta_input)

    # 3. 构造 Docker 命令
    # 我们不拼接字符串，而是使用列表传参，让 subprocess 处理转义，这是最安全的做法
    cmd = [
        "docker-compose", "exec", "-T", "-u", "www-data", 
        "wordpress", "wp", "post", "create",
        "--post_type=post",
        "--post_status=publish",
        "--post_author=1",  # 假设 admin ID 为 1
        f"--post_date={date_gmt}",
        f"--post_title={title}",
        f"--post_content={content}", # 此时 content 已经是 HTML
        f"--meta_input={meta_json}",
        "--porcelain" # 只输出新文章的 ID
    ]

    try:
        # 4. 执行命令
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        new_post_id = result.stdout.strip()
        
        with print_lock:
            global success_count
            success_count += 1
            print(f"✅ [{success_count}] Imported: {title[:30]}... (ID: {new_post_id})")
            
    except subprocess.CalledProcessError as e:
        with print_lock:
            global fail_count
            fail_count += 1
            print(f"❌ Failed: {title[:30]}...")
            print(f"   Error: {e.stderr}")

def main():
    # 检查文件是否存在
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found in current directory.")
        return

    print(f"📂 Loading {JSON_FILE}...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_articles = len(data)
    print(f"🚀 Starting parallel import for {total_articles} articles with {MAX_WORKERS} workers...")
    
    if HAS_MARKDOWN:
        print("✨ Markdown processing enabled.")
    else:
        print("⚠️ Markdown processing disabled (library not found).")

    start_time = time.time()

    # 使用线程池并发执行
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(import_single_article, article) for article in data]
        
        # 等待所有任务完成
        concurrent.futures.wait(futures)

    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "="*30)
    print(f"🎉 Import Completed!")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"⏱️  Time Taken: {duration:.2f} seconds")
    print(f"🚀 Speed: {total_articles / duration:.2f} articles/sec")
    print("="*30)

if __name__ == "__main__":
    main()