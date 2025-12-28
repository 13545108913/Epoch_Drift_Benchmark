import json
import trafilatura
from trafilatura.settings import use_config
import requests
import time
import feedparser
from urllib.parse import urlparse, urljoin
import logging
import random
from datetime import datetime
import hashlib
import os
from bs4 import BeautifulSoup
import re
import concurrent.futures
from threading import Lock, RLock
import queue
from collections import Counter

# --- 配置部分 ---

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定义关键词映射
CATEGORY_KEYWORDS = {
    "technology": ["ai", "artificial intelligence", "code", "programming", "software", "linux", "github", "python", "java", "developer", "cloud", "aws", "google", "microsoft", "apple", "app", "cyber", "data", "algorithm"],
    "business": ["market", "stock", "economy", "finance", "trade", "investment", "ceo", "company", "startup", "money", "bank", "inflation", "revenue"],
    "science": ["space", "nasa", "physics", "biology", "climate", "research", "study", "scientist", "planet", "energy", "lab", "discovery"],
    "health": ["medical", "health", "doctor", "virus", "cancer", "diet", "nutrition", "mental", "hospital", "patient", "drug", "medicine"],
    "politics": ["government", "election", "president", "law", "policy", "senate", "congress", "minister", "vote", "campaign", "diplomacy"],
    "entertainment": ["movie", "film", "music", "star", "celebrity", "actor", "game", "show", "series", "hollywood", "concert"],
    "sports": ["football", "basketball", "soccer", "olympic", "league", "team", "player", "championship", "score", "match"]
}

SOURCES = [
    # 新闻媒体 - 国际
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
    "https://rss.cnn.com/rss/edition_technology.rss",
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.reuters.com/reuters/businessNews",
    
    # 科技与开发
    "https://dev.to/feed",
    "https://stackoverflow.blog/feed/",
    "https://blog.github.com/feed.xml",
    "https://aws.amazon.com/blogs/aws/feed/",
    "https://cloud.google.com/blog/feeds/gcp",
    "https://blog.google/technology/ai/rss/",
    "https://blogs.microsoft.com/ai/feed/",
    
    # 教程与知识
    "https://www.wikihow.com/feed.rss",
    "https://www.lifehack.org/feed",
    "https://www.howtogeek.com/feed/",
    "https://www.digitalocean.com/community/tutorials/feed",
    
    # 商业与金融
    "https://www.bloomberg.com/feeds/podcasts/etf-report.xml",
    "https://www.forbes.com/business/feed/",
    "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_articles",
    
    # 科学与教育
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://phys.org/rss-feed/",
    "https://www.nature.com/nature.rss",
    "https://www.science.org/rss/news_current.xml",
    
    # 健康与医疗
    "https://www.mayoclinic.org/rss/all-health-information-topics",
    "https://www.health.harvard.edu/blog/feed",
    "https://www.webmd.com/rss/default.aspx",
    
    # 编程与技术博客
    "https://blog.codinghorror.com/rss/",
    "https://martinfowler.com/feed.atom",
    "https://davidwalsh.name/feed",
    "https://css-tricks.com/feed/",
    "https://reactjs.org/feed.xml",
    
    # 区域新闻 - 多语言多地区
    "https://feeds.feedburner.com/AlJazeeraEnglish",
    "https://www.france24.com/en/rss",
    "https://www.dw.com/rss/en-news/s-31519",
    "https://www.scmp.com/rss/91/feed",
    
    # 开源与Linux
    "https://opensource.com/feed",
    "https://www.linuxfoundation.org/feed/",
    "https://www.linux.com/feed/",
]

OUTPUT_FILE = "diverse_real_world_data.json"
VISITED_URLS_FILE = "visited_urls.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 全局锁
visited_urls_lock = RLock()
collected_data_lock = RLock()
content_hashes_lock = RLock()

class ArticleCollector:
    def __init__(self, max_articles=500, max_workers=10):
        self.max_articles = max_articles
        self.max_workers = max_workers
        self.collected_data = []
        self.visited_urls = set()
        self.content_hashes = set()
        self.progress_counter = 0
        self.article_queue = queue.Queue()
        self.all_sources_processed = False
        
        # Trafilatura 配置
        self.traf_config = use_config()
        self.traf_config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")

    def load_visited_urls(self):
        if os.path.exists(VISITED_URLS_FILE):
            try:
                with open(VISITED_URLS_FILE, 'r', encoding='utf-8') as f:
                    self.visited_urls = set(json.load(f))
            except:
                self.visited_urls = set()
        logger.info(f"已加载 {len(self.visited_urls)} 个已访问URL")

    def save_visited_urls(self):
        with visited_urls_lock:
            with open(VISITED_URLS_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(self.visited_urls), f, ensure_ascii=False, indent=2)

    def is_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def calculate_content_hash(self, content):
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def extract_comments_bs4(self, soup):
        comments = []
        comment_selectors = [
            '#comments', '.comments-area', '.comment-list', 
            '#disqus_thread', '.discussion', '[data-testid="comment-list"]'
        ]
        
        comment_area = None
        for selector in comment_selectors:
            comment_area = soup.select_one(selector)
            if comment_area:
                break
        
        if comment_area:
            comment_items = comment_area.find_all(['li', 'article', 'div'], class_=re.compile(r'comment|review|post'))
            if not comment_items:
                raw_text = comment_area.get_text(separator='\n').strip()
                lines = [line.strip() for line in raw_text.split('\n') if len(line.strip()) > 10]
                comments = lines[:10]
            else:
                for item in comment_items[:10]:
                    text = item.get_text(separator=' ').strip()
                    if len(text) > 5:
                        comments.append(re.sub(r'\s+', ' ', text))
        return comments

    def bs4_to_markdown_with_images(self, element, base_url):
        """
        [新增功能] 将 BS4 元素转换为 Markdown，特别保留图片链接
        """
        if not element:
            return ""
            
        content_parts = []
        
        # 查找所有关键标签：段落、标题、列表、图片、Figure
        tags_to_find = ['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'img', 'figure', 'pre', 'code']
        
        # 递归或遍历子元素
        # 这里使用简化逻辑：查找所有直接的子块级元素，如果不是直接子元素，Trafilatura 通常更好
        # 这里为了Fallback，我们遍历所有后代中的关键标签
        for tag in element.find_all(tags_to_find):
            
            # --- 处理图片 ---
            if tag.name == 'img':
                # 处理懒加载 (data-src) 和 相对路径
                src = tag.get('src') or tag.get('data-src') or tag.get('data-original')
                if src:
                    # 过滤掉 base64 小图标或无效图
                    if src.startswith('data:image'):
                        continue
                        
                    # 转换为绝对路径
                    full_src = urljoin(base_url, src)
                    alt = tag.get('alt', '').strip()
                    # 生成 Markdown 图片语法
                    content_parts.append(f"\n![{alt}]({full_src})\n")
            
            elif tag.name == 'figure':
                img = tag.find('img')
                if img:
                    src = img.get('src') or img.get('data-src')
                    if src and not src.startswith('data:image'):
                        full_src = urljoin(base_url, src)
                        caption = tag.find('figcaption')
                        alt = caption.get_text().strip() if caption else img.get('alt', '').strip()
                        content_parts.append(f"\n![{alt}]({full_src})\n")
            
            # --- 处理文本 ---
            elif tag.name in ['p', 'li']:
                text = tag.get_text(separator=' ').strip()
                if text:
                    prefix = "- " if tag.name == 'li' else ""
                    content_parts.append(f"{prefix}{text}")
            
            elif tag.name.startswith('h'):
                text = tag.get_text(separator=' ').strip()
                if text:
                    level = int(tag.name[1])
                    content_parts.append(f"{'#' * level} {text}")
            
            elif tag.name == 'pre':
                code = tag.get_text().strip()
                content_parts.append(f"```\n{code}\n```")

        # 简单的去重和清理：因为 find_all 会递归，可能导致父元素和子元素内容重复
        # 这是一个简化的 Fallback，主要依赖 Trafilatura，这里不做过复杂的去重
        return '\n\n'.join(content_parts)

    def extract_with_enhanced_data(self, html_content, url):
        """
        提取内容、作者、评论和元数据，确保包含图片
        """
        result = {
            "content": None,
            "author": None,
            "comments": [],
            "keywords": [] 
        }
        
        # 1. Trafilatura: 开启图片提取
        try:
            traf_data = trafilatura.bare_extraction(
                html_content, 
                url=url, 
                include_comments=False, 
                output_format="markdown",
                include_images=True,  # <--- 关键修改：启用图片
                include_tables=True,
                config=self.traf_config
            )
            
            if traf_data:
                if hasattr(traf_data, 'as_dict'):
                    traf_data = traf_data.as_dict()

                result["content"] = traf_data.get('text')
                result["author"] = traf_data.get('author')
                
                if traf_data.get('categories'):
                    result["keywords"].extend(traf_data.get('categories'))
                if traf_data.get('tags'):
                    result["keywords"].extend(traf_data.get('tags'))
                    
        except Exception as e:
            logger.warning(f"Trafilatura 提取失败: {e}")

        # 2. BeautifulSoup 补全逻辑 (优化版，支持图片)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 移除干扰元素
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe', 'svg']):
            element.decompose()

        # 补全 Content (如果 Trafilatura 失败或内容太短)
        if not result["content"] or len(result["content"]) < 300:
            main_content = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|post|article|entry'))
            
            if main_content:
                # 使用自定义的转换函数，而不是 get_text()
                result["content"] = self.bs4_to_markdown_with_images(main_content, url)
            elif soup.body:
                result["content"] = self.bs4_to_markdown_with_images(soup.body, url)

        # 补全 Author
        if not result["author"]:
            meta_author = soup.find('meta', attrs={'name': 'author'}) or soup.find('meta', property='article:author')
            if meta_author:
                result["author"] = meta_author.get('content')
            else:
                author_tag = soup.find(class_=re.compile(r'author-name|byline|posted-by'))
                if author_tag:
                    result["author"] = author_tag.get_text().strip()

        # 提取 Meta Keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            result["keywords"].extend([k.strip() for k in meta_keywords.get('content').split(',')])

        # 提取评论
        result["comments"] = self.extract_comments_bs4(soup)

        return result

    def infer_category(self, source_url, title, content, rss_tags=None, meta_keywords=None):
        # 1. 优先使用 RSS 源提供的 Tags
        if rss_tags:
            for tag in rss_tags:
                tag_lower = tag.lower()
                for cat, keywords in CATEGORY_KEYWORDS.items():
                    if tag_lower == cat or tag_lower in keywords:
                        return cat

        # 2. 准备文本用于分析
        text_to_analyze = (title + " " + (content[:2000] if content else "")).lower()
        if meta_keywords:
            text_to_analyze += " " + " ".join(meta_keywords).lower()

        # 3. 基于关键词权重的打分系统
        scores = Counter()
        
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text_to_analyze):
                    scores[category] += 1
                    if keyword in title.lower():
                        scores[category] += 2

        if scores:
            best_category = scores.most_common(1)[0][0]
            return best_category

        # 4. 基于 URL 的兜底
        source_lower = source_url.lower()
        if 'tech' in source_lower or 'dev' in source_lower or 'code' in source_lower:
            return "technology"
        elif 'money' in source_lower or 'business' in source_lower:
            return "business"
        elif 'health' in source_lower:
            return "health"
        elif 'sci' in source_lower:
            return "science"
            
        return "general"

    def process_article(self, entry, source):
        url = getattr(entry, 'link', '')
        if not self.is_valid_url(url):
            return None
            
        with visited_urls_lock:
            if url in self.visited_urls:
                return None
            self.visited_urls.add(url)
        
        time.sleep(random.uniform(0.5, 2))
        
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            })
            
            response = session.get(url, timeout=10)
            
            if response.status_code == 200:
                extracted_data = self.extract_with_enhanced_data(response.text, url)
                content = extracted_data["content"]
                
                if content and len(content.strip()) > 200:
                    content_hash = self.calculate_content_hash(content)
                    
                    with content_hashes_lock:
                        if content_hash in self.content_hashes:
                            return None
                        self.content_hashes.add(content_hash)
                    
                    rss_tags = []
                    if hasattr(entry, 'tags'):
                        rss_tags = [t.term for t in entry.tags]
                    
                    rss_author = getattr(entry, 'author', None)
                    final_author = extracted_data["author"] or rss_author or "Unknown"

                    category = self.infer_category(
                        source, 
                        entry.title, 
                        content, 
                        rss_tags=rss_tags, 
                        meta_keywords=extracted_data["keywords"]
                    )

                    published = getattr(entry, 'published', getattr(entry, 'updated', datetime.now().isoformat()))

                    article_data = {
                        "id": hashlib.md5(url.encode()).hexdigest(),
                        "title": entry.title.strip(),
                        "content": content.strip(),
                        "author": final_author,
                        "comments": extracted_data["comments"],
                        "source_url": url,
                        "source_feed": source,
                        "published_date": published,
                        "crawl_timestamp": datetime.now().isoformat(),
                        "content_length": len(content),
                        "language": "en",
                        "category": category,
                        "tags": rss_tags + extracted_data["keywords"],
                        "content_hash": content_hash
                    }
                    
                    return article_data
            else:
                logger.warning(f"HTTP {response.status_code}: {url}")
                
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
        
        return None

    def process_feed_source(self, source):
        logger.info(f"正在解析源: {source}")
        try:
            feed = feedparser.parse(source)
            if not feed.entries:
                return []
            entries = list(feed.entries)
            random.shuffle(entries)
            for entry in entries:
                if len(self.collected_data) >= self.max_articles:
                    break
                self.article_queue.put((entry, source))
            return entries
        except Exception as e:
            logger.error(f"RSS Error {source}: {e}")
            return []

    def worker_thread(self, worker_id):
        logger.info(f"工作线程 {worker_id} 启动")
        while True:
            try:
                entry, source = self.article_queue.get(timeout=3)
                if len(self.collected_data) >= self.max_articles:
                    self.article_queue.task_done()
                    break
                
                article_data = self.process_article(entry, source)
                if article_data:
                    with collected_data_lock:
                        if len(self.collected_data) < self.max_articles:
                            self.collected_data.append(article_data)
                            self.progress_counter += 1
                            logger.info(f"[{self.progress_counter}] [{article_data['category'].upper()}] {article_data['title'][:40]}... (Img:{'!' in article_data['content']})")
                            if self.progress_counter % 20 == 0:
                                self.save_progress()
                self.article_queue.task_done()
            except queue.Empty:
                if self.all_sources_processed:
                    break
            except Exception as e:
                logger.error(f"Thread error: {e}")
                break

    def save_progress(self):
        temp_file = OUTPUT_FILE + ".temp"
        with collected_data_lock:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.collected_data, f, ensure_ascii=False, indent=2)

    def save_final_data(self):
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.collected_data, f, ensure_ascii=False, indent=2)
        self.save_visited_urls()
        cats = Counter(d['category'] for d in self.collected_data)
        logger.info(f"分类统计: {dict(cats)}")

    def fetch_articles_parallel(self):
        self.load_visited_urls()
        random.shuffle(SOURCES)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self.process_feed_source, SOURCES)
        
        self.all_sources_processed = True
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.worker_thread, i) for i in range(self.max_workers)]
            concurrent.futures.wait(futures)
            
        self.save_final_data()
        return self.collected_data

if __name__ == "__main__":
    collector = ArticleCollector(max_articles=600, max_workers=8)
    collector.fetch_articles_parallel()