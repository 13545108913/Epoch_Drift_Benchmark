import json
import subprocess
import concurrent.futures
import datetime
import os
import time
from threading import Lock

# =======================================
# 尝试导入 markdown
# =======================================
try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    print("⚠️  Warning: 'markdown' library not found. Falling back to simple text formatting.")

# ================= 配置 =================
JSON_FILE = 'diverse_real_world_data.json'
MAX_WORKERS = 5
WP_USER = 'admin'
# =======================================

print_lock = Lock()
success_count = 0
fail_count = 0

def parse_date(date_str):
    """
    适配多种日期格式
    """
    try:
        # 1. 尝试带时区偏移量的格式 (例如 +0000)
        dt = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            # 2. 尝试 GMT 文本格式
            dt = datetime.datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            # 3. 兜底
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def process_content(raw_content):
    if not raw_content:
        return ""
    if HAS_MARKDOWN:
        return markdown.markdown(raw_content, extensions=['extra'])
    else:
        lines = raw_content.split('\n\n')
        paragraphs = [f'<p>{line.strip().replace(chr(10), "<br>")}</p>' for line in lines if line.strip()]
        return ''.join(paragraphs)

def ensure_category_exists(category_name):
    if not category_name:
        return
    cmd = [
        "docker-compose", "exec", "-T", "-u", "www-data",
        "wordpress", "wp", "term", "create",
        "category", category_name
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True)
    except Exception:
        pass

def set_post_category(post_id, category_name):
    if not category_name:
        return
    cmd = [
        "docker-compose", "exec", "-T", "-u", "www-data",
        "wordpress", "wp", "post", "term", "set",
        str(post_id), "category", category_name
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        pass

def import_single_article(article):
    global success_count, fail_count
    
    # 1. 基础字段
    title = article.get('title', 'Untitled')
    raw_content = article.get('content', '')
    content = process_content(raw_content)
    date_gmt = parse_date(article.get('published_date', ''))
    
    # 2. 提取分类和标签
    tags_list = article.get('tags', [])
    tags_input = ','.join(tags_list) if tags_list else ''
    category_name = article.get('category', '')
    
    # 3. 提取作者信息
    # 如果 JSON 中没有 author，默认为空字符串或 'Unknown'
    original_author = article.get('author', '')

    # 4. 构造 Meta Data
    # 将作者存入 'original_author' 字段
    meta_input = {
        'original_id': article.get('id'),
        'original_author': original_author,  # <--- 新增：这里存入作者名
        'source_url': article.get('source_url'),
        'crawl_timestamp': article.get('crawl_timestamp'),
        'content_hash': article.get('content_hash'),
        'source_feed': article.get('source_feed')
    }
    meta_json = json.dumps(meta_input)

    # 5. 构造命令
    cmd = [
        "docker-compose", "exec", "-T", "-u", "www-data", 
        "wordpress", "wp", "post", "create",
        "--post_type=post",
        "--post_status=publish",
        "--post_author=1", # 这里仍然使用 ID=1 (管理员) 作为发布者
        f"--post_date={date_gmt}",
        f"--post_title={title}",
        f"--post_content={content}",
        f"--meta_input={meta_json}", # 元数据将包含作者信息
        "--porcelain"
    ]

    if tags_input:
        cmd.append(f"--tags_input={tags_input}")

    try:
        # A. 创建文章
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        new_post_id = result.stdout.strip()
        
        # B. 设置分类
        if category_name:
            ensure_category_exists(category_name)
            set_post_category(new_post_id, category_name)

        with print_lock:
            global success_count
            success_count += 1
            # 打印包含作者的日志
            auth_info = f"[Auth: {original_author[:10]}]" if original_author else ""
            print(f"✅ [{success_count}] Imported: {title[:15]}... (ID: {new_post_id}) {auth_info}")
            
    except subprocess.CalledProcessError as e:
        with print_lock:
            global fail_count
            fail_count += 1
            print(f"❌ Failed: {title[:30]}...")
            print(f"   Error: {e.stderr}")

def main():
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found.")
        return

    print(f"📂 Loading {JSON_FILE}...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    print(f"🚀 Starting import for {total} articles (including Author data)...")
    
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(import_single_article, article) for article in data]
        concurrent.futures.wait(futures)

    duration = time.time() - start_time
    print(f"\n🎉 Completed! Success: {success_count}, Failed: {fail_count}, Time: {duration:.2f}s")

if __name__ == "__main__":
    main()