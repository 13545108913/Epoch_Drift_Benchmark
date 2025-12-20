import json
import trafilatura
import requests
import time
import feedparser
from urllib.parse import urlparse
import logging
import random
from datetime import datetime, timedelta
import hashlib
import os
from bs4 import BeautifulSoup
import re
import concurrent.futures
from threading import Lock
import queue

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 扩展数据源 - 涵盖多个领域和地区
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

# 扩展User-Agent列表，增加多样性
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
]

# 全局锁和共享数据结构
visited_urls_lock = Lock()
collected_data_lock = Lock()
content_hashes_lock = Lock()

class ArticleCollector:
    def __init__(self, max_articles=500, max_workers=10):
        self.max_articles = max_articles
        self.max_workers = max_workers
        self.collected_data = []
        self.visited_urls = set()
        self.content_hashes = set()
        self.progress_counter = 0
        self.article_queue = queue.Queue()
        
    def load_visited_urls(self):
        """加载已访问的URL列表"""
        if os.path.exists(VISITED_URLS_FILE):
            with open(VISITED_URLS_FILE, 'r', encoding='utf-8') as f:
                self.visited_urls = set(json.load(f))
        logger.info(f"已加载 {len(self.visited_urls)} 个已访问URL")

    def save_visited_urls(self):
        """保存已访问的URL列表"""
        with visited_urls_lock:
            with open(VISITED_URLS_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(self.visited_urls), f, ensure_ascii=False, indent=2)

    def is_valid_url(self, url):
        """验证URL是否有效"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def calculate_content_hash(self, content):
        """计算内容哈希值用于去重"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def extract_with_fallback(self, html_content, url):
        """使用多种方法提取内容"""
        content = None
        
        # 方法1: 使用trafilatura提取
        try:
            content = trafilatura.extract(
                html_content, 
                output_format="markdown",
                include_comments=False, 
                include_tables=True,
                include_images=True,
                no_fallback=False
            )
        except Exception as e:
            logger.warning(f"trafilatura提取失败: {e}")
        
        # 方法2: 如果trafilatura失败，使用BeautifulSoup提取
        if not content or len(content.strip()) < 300:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 移除不需要的元素
                for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                    element.decompose()
                
                # 尝试找到主要内容区域
                main_content = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|post|article'))
                
                if main_content:
                    # 提取文本
                    paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                    content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                else:
                    # 回退到body提取
                    body = soup.find('body')
                    if body:
                        paragraphs = body.find_all(['p', 'h1', 'h2', 'h3'])
                        content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                        
            except Exception as e:
                logger.warning(f"BeautifulSoup提取失败: {e}")
        
        return content

    def should_include_article(self, content, title, min_length=500, max_length=50000):
        """判断是否应该包含这篇文章"""
        if not content or not title:
            return False
        
        content = content.strip()
        title = title.strip()
        
        # 检查长度
        if len(content) < min_length or len(content) > max_length:
            return False
        
        # 检查内容质量 - 简单的启发式规则
        lines = content.split('\n')
        if len(lines) < 3:
            return False
        
        # 检查是否有足够的句子
        sentences = re.split(r'[.!?]+', content)
        if len([s for s in sentences if len(s.strip()) > 20]) < 3:
            return False
        
        return True

    def get_random_headers(self):
        """生成随机请求头"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }

    def process_article(self, entry, source):
        """处理单篇文章的采集任务"""
        url = getattr(entry, 'link', '')
        
        # 检查URL有效性
        if not self.is_valid_url(url):
            return None
            
        # 检查是否已访问（使用锁保证线程安全）
        with visited_urls_lock:
            if url in self.visited_urls:
                return None
            self.visited_urls.add(url)
        
        # 随机延迟，避免被封
        time.sleep(random.uniform(1, 3))
        
        try:
            session = requests.Session()
            session.headers.update(self.get_random_headers())
            
            response = session.get(url, timeout=15)
            
            if response.status_code == 200:
                content = self.extract_with_fallback(response.text, url)
                
                if self.should_include_article(content, entry.title):
                    content_hash = self.calculate_content_hash(content)
                    
                    # 检查内容重复（使用锁保证线程安全）
                    with content_hashes_lock:
                        if content_hash in self.content_hashes:
                            return None
                        self.content_hashes.add(content_hash)
                    
                    # 提取发布日期
                    published = getattr(entry, 'published', '')
                    if not published and hasattr(entry, 'updated'):
                        published = entry.updated
                    
                    article_data = {
                        "id": hashlib.md5(url.encode()).hexdigest(),
                        "title": entry.title.strip(),
                        "content": content.strip(),
                        "source_url": url,
                        "source_feed": source,
                        "published_date": published,
                        "crawl_timestamp": datetime.now().isoformat(),
                        "content_length": len(content),
                        "language": "en",
                        "category": self.infer_category(source, entry.title, content),
                        "content_hash": content_hash
                    }
                    
                    return article_data
                else:
                    logger.debug(f"内容不符合要求: {url}")
            else:
                logger.warning(f"HTTP {response.status_code} - 请求被拒绝: {url}")
                
        except requests.RequestException as e:
            logger.error(f"网络错误: {e} - {url}")
        except Exception as e:
            logger.error(f"处理文章时出错: {e} - {url}")
        
        return None

    def process_feed_source(self, source):
        """处理单个RSS源的任务"""
        logger.info(f"正在解析源: {source}")
        
        try:
            session = requests.Session()
            session.headers.update(self.get_random_headers())
            
            feed = feedparser.parse(source)
            
            if not feed.entries:
                logger.warning(f"无法从 {source} 解析到文章")
                return []
            
            logger.info(f"从 {source} 找到 {len(feed.entries)} 篇文章")
            
            # 随机打乱文章顺序，避免总是采集最新的
            entries = list(feed.entries)
            random.shuffle(entries)
            
            # 将文章任务加入队列
            for entry in entries:
                if len(self.collected_data) >= self.max_articles:
                    break
                self.article_queue.put((entry, source))
                
            return entries
            
        except Exception as e:
            logger.error(f"处理源 {source} 时出错: {e}")
            return []

    def worker_thread(self, worker_id):
        """工作线程函数"""
        logger.info(f"工作线程 {worker_id} 启动")
        
        while True:
            try:
                # 非阻塞获取任务，超时3秒
                entry, source = self.article_queue.get(timeout=3)
                
                # 检查是否已达到目标数量
                if len(self.collected_data) >= self.max_articles:
                    break
                
                # 处理文章
                article_data = self.process_article(entry, source)
                
                if article_data:
                    with collected_data_lock:
                        self.collected_data.append(article_data)
                        self.progress_counter += 1
                        
                    logger.info(f"[线程{worker_id}] [{self.progress_counter}/{self.max_articles}] 成功提取: {article_data['title'][:60]}... ({len(article_data['content'])} 字符)")
                    
                    # 定期保存进度
                    if self.progress_counter % 20 == 0:
                        self.save_progress()
                        
                self.article_queue.task_done()
                
            except queue.Empty:
                # 队列为空，检查是否所有源都已处理完
                if self.all_sources_processed:
                    break
                continue
            except Exception as e:
                logger.error(f"工作线程 {worker_id} 出错: {e}")
                break
        
        logger.info(f"工作线程 {worker_id} 退出")

    def fetch_articles_parallel(self):
        """并行采集文章"""
        self.load_visited_urls()
        
        logger.info(f"开始并行采集，目标: {self.max_articles} 篇文章，使用 {self.max_workers} 个工作线程")
        
        # 随机打乱源顺序，增加多样性
        random.shuffle(SOURCES)
        
        # 第一阶段：并行解析所有RSS源
        logger.info("第一阶段：解析RSS源...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, self.max_workers)) as executor:
            future_to_source = {executor.submit(self.process_feed_source, source): source for source in SOURCES}
            
            for future in concurrent.futures.as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"处理源 {source} 时出错: {e}")
        
        # 标记所有源已处理完成
        self.all_sources_processed = True
        logger.info(f"RSS源解析完成，队列中有 {self.article_queue.qsize()} 篇文章待处理")
        
        # 第二阶段：并行处理文章采集
        logger.info("第二阶段：并行采集文章内容...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 启动工作线程
            worker_futures = [executor.submit(self.worker_thread, i) for i in range(self.max_workers)]
            
            # 等待所有工作线程完成
            concurrent.futures.wait(worker_futures)
        
        # 最终保存
        self.save_final_data()
        return self.collected_data

    def infer_category(self, source, title, content):
        """根据源、标题和内容推断类别"""
        title_lower = title.lower()
        content_lower = content.lower()[:1000]  # 只检查前1000个字符
        
        # 基于源的类别推断
        if 'tech' in source.lower() or 'programming' in source.lower() or 'dev' in source.lower():
            return "technology"
        elif 'business' in source.lower() or 'finance' in source.lower() or 'reuters' in source.lower():
            return "business"
        elif 'health' in source.lower() or 'medical' in source.lower():
            return "health"
        elif 'science' in source.lower() or 'nasa' in source.lower():
            return "science"
        elif 'how-to' in source.lower() or 'tutorial' in source.lower():
            return "tutorial"
        else:
            return "general"

    def save_progress(self):
        """保存进度"""
        temp_file = OUTPUT_FILE + ".temp"
        with collected_data_lock:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.collected_data, f, ensure_ascii=False, indent=2)
        self.save_visited_urls()
        logger.info(f"💾 已保存进度: {len(self.collected_data)} 篇")

    def save_final_data(self):
        """保存最终数据"""
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.collected_data, f, ensure_ascii=False, indent=2)
        self.save_visited_urls()
        
        logger.info(f"💾 数据已保存至 {OUTPUT_FILE}，共 {len(self.collected_data)} 篇")
        
        # 打印统计信息
        if self.collected_data:
            total_chars = sum(len(article["content"]) for article in self.collected_data)
            avg_chars = total_chars // len(self.collected_data)
            
            categories = {}
            for article in self.collected_data:
                cat = article.get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1
            
            logger.info(f"📊 内容统计:")
            logger.info(f"   总字符数: {total_chars}")
            logger.info(f"   平均每篇: {avg_chars} 字符")
            logger.info(f"   类别分布: {categories}")

def analyze_dataset():
    """分析数据集质量"""
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📈 数据集分析:")
        print(f"   文章总数: {len(data)}")
        
        # 内容长度分布
        lengths = [len(article['content']) for article in data]
        print(f"   平均长度: {sum(lengths)//len(lengths)} 字符")
        print(f"   最短文章: {min(lengths)} 字符")
        print(f"   最长文章: {max(lengths)} 字符")
        
        # 类别分布
        categories = {}
        for article in data:
            cat = article.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"   类别分布:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"     {cat}: {count} 篇")
        
        # 源分布
        sources = {}
        for article in data:
            source = article.get('source_feed', 'unknown')
            try:
                domain = urlparse(source).netloc if source else 'unknown'
                sources[domain] = sources.get(domain, 0) + 1
            except:
                sources['unknown'] = sources.get('unknown', 0) + 1
        
        print(f"   来源分布 (前10):")
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"     {source}: {count} 篇")
            
    except FileNotFoundError:
        print("数据文件不存在")

if __name__ == "__main__":
    start_time = time.time()
    
    try:
        # 可调整参数
        MAX_ARTICLES = 500
        MAX_WORKERS = 8  # 根据网络情况和目标网站调整
        
        collector = ArticleCollector(max_articles=MAX_ARTICLES, max_workers=MAX_WORKERS)
        articles = collector.fetch_articles_parallel()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n🎉 并行采集完成!")
        print(f"   耗时: {duration:.2f} 秒")
        print(f"   成功采集: {len(articles)} 篇文章")
        print(f"   平均速度: {len(articles)/duration:.2f} 篇/秒")
        print(f"   使用线程数: {MAX_WORKERS}")
        
        # 分析数据集
        analyze_dataset()
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断采集")
    except Exception as e:
        logger.error(f"采集过程中发生严重错误: {e}")