import json
import random
import os

# ================= 配置 =================
INPUT_FILE = 'diverse_real_world_data.json'
OUTPUT_FILE = 'benchmark_tasks.json'
TASKS_PER_TEMPLATE = 8  # 每个模版生成的任务数量
# =======================================

def load_data():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found. using dummy data.")
        return []
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_tasks(articles):
    tasks = []
    task_id_counter = 0

    # 提取基础数据池
    titles = [a.get('title') for a in articles if a.get('title')]
    categories = list(set([a.get('category') for a in articles if a.get('category')]))
    if not categories: categories = ['Uncategorized'] # 兜底

    # --- 辅助函数：添加任务 ---
    def add_task(template, params):
        nonlocal task_id_counter
        # 替换模版中的变量
        intent = template
        for key, value in params.items():
            intent = intent.replace(f"{{{{{key}}}}}", str(value))
        
        tasks.append({
            "sites": ["wordpress"],
            "task_id": task_id_counter,
            "start_url": "__WORDPRESS__",
            "intent_template": template,
            "instantiation_dict": params,
            "intent": intent,
            "eval": {
                "eval_types": ["url_match"],
                "reference_answers": None,
                "reference_url": "__WORDPRESS__",
                "program_html": [],
                "url_note": "GOLD in PRED"
            }
        })
        task_id_counter += 1

    print(f"🔄 Generating tasks based on {len(articles)} articles...")

    # ---------------------------------------------------------
    # Template 1: "Find the article titled {{title}}."
    # ---------------------------------------------------------
    template_1 = "Find the article titled {{title}}."
    # 随机抽取 N 个标题
    selected_titles = random.sample(titles, min(len(titles), TASKS_PER_TEMPLATE))
    for title in selected_titles:
        add_task(template_1, {"title": f"'{title}'"})

    # ---------------------------------------------------------
    # Template 2: "Identify the {{info1}} and the {{info2}} of {{adj}} post on the homepage."
    # ---------------------------------------------------------
    template_2 = "Identify the {{info1}} and the {{info2}} of {{adj}} post on the homepage."
    infos = ["author name", "publish date", "title", "category"]
    adjs = ["most recent", "first", "latest", "top"]
    
    for _ in range(TASKS_PER_TEMPLATE):
        info1, info2 = random.sample(infos, 2)
        adj = random.choice(adjs)
        add_task(template_2, {
            "info1": info1, 
            "info2": info2, 
            "adj": adj
        })

    # ---------------------------------------------------------
    # Template 3: "Use the site search bar to search for the keyword {{target_word}}, and click on the {{adj}} result."
    # ---------------------------------------------------------
    template_3 = "Use the site search bar to search for the keyword {{target_word}}, and click on the {{adj}} result."
    ordinals = ["first", "second", "third"]
    
    # 从标题中提取关键词 (长度大于4的单词)
    all_words = []
    for t in titles:
        all_words.extend([w for w in t.split() if len(w) > 4])
    if not all_words: all_words = ["Target"]

    for _ in range(TASKS_PER_TEMPLATE):
        target_word = random.choice(all_words)
        # 去除标点
        target_word = ''.join(e for e in target_word if e.isalnum())
        adj = random.choice(ordinals)
        add_task(template_3, {
            "target_word": f"'{target_word}'",
            "adj": adj
        })

    # ---------------------------------------------------------
    # Template 4: "Navigate to the {{category}} category page."
    # ---------------------------------------------------------
    template_4 = "Navigate to the {{category}} category page."
    # 循环使用现有分类
    for i in range(len(categories)):
        cat = categories[i]
        add_task(template_4, {"category": f"'{cat}'"})

    # ---------------------------------------------------------
    # Template 5: "Find the link to the {{element}} and click it."
    # ---------------------------------------------------------
    template_5 = "Find the link to the {{element}} and click it."
    elements = ["Next Post", "Previous Post", "Home", "About", "RSS Feed", "Comments"]
    
    for i in range(6):
        element = elements[i]
        add_task(template_5, {"element": f"'{element}'"})

    # ---------------------------------------------------------
    # Template 6: "Go to the {{title}} post and leave a comment saying: {{content}}."
    # ---------------------------------------------------------
    template_6 = "Go to the {{title}} post and leave a comment saying: {{content}}."
    comments = [
        # 积极反馈
        "Great article!",
        "Excellent write-up!",
        "Very informative post.",
        "Well written and easy to understand.",
        "This is exactly what I was looking for.",
        
        # 感谢类
        "Thanks for sharing.",
        "Thank you for this helpful guide.",
        "Appreciate the detailed explanation.",
        "Thanks, this solved my problem.",
        "Grateful for this resource.",
        
        # 观点类
        "Interesting perspective.",
        "Never thought about it this way.",
        "This gives me a new angle to consider.",
        "Fascinating approach.",
        "Unique viewpoint.",
    ]
    
    selected_titles_6 = random.sample(titles, min(len(titles), TASKS_PER_TEMPLATE))
    for title in selected_titles_6:
        content = random.choice(comments)
        add_task(template_6, {
            "title": f"'{title}'", 
            "content": f"'{content}'"
        })

    # ---------------------------------------------------------
    # Template 7: "Find the {{element}} section and click on the link corresponding to {{adj}} recent one."
    # ---------------------------------------------------------
    template_7 = "Find the {{element}} section and click on the link corresponding to {{adj}} recent one."
    sections = ["Recent Posts", "Recent Comments", "Archives", "Categories"]
    ordinals_7 = ["most", "second most", "third most"]
    
    for _ in range(TASKS_PER_TEMPLATE):
        section = random.choice(sections)
        adj = random.choice(ordinals_7)
        add_task(template_7, {
            "element": f"'{section}'",
            "adj": adj
        })

    # ... (保留原有的 Template 1-7 代码) ...

    # =========================================================
    # 数据预处理扩展 (为新任务准备数据)
    # =========================================================
    # 提取或生成标签 (Tags)
    all_tags = []
    for a in articles:
        # 如果JSON里有tags字段则读取，否则从标题里提取单词作为伪标签
        if 'tags' in a and isinstance(a['tags'], list):
            all_tags.extend(a['tags'])
        else:
            all_tags.extend([w for w in a.get('title', '').split() if len(w) > 5])
    
    # 去重并提供兜底数据
    unique_tags = list(set(all_tags))
    if not unique_tags: unique_tags = ["news", "update", "featured", "tech"]

    # 提取作者 (Authors) - 默认为 admin
    authors = list(set([a.get('author') for a in articles if a.get('author')]))
    if not authors: authors = ["admin", "editor"]

    # =========================================================
    # 新增扩展模版 (Template 8 - 13)
    # =========================================================

    # ---------------------------------------------------------
    # Template 8: Tag Navigation (标签云/标签页测试)
    # "Navigate to the tag archive for {{tag}} and verify if the page title contains the tag name."
    # ---------------------------------------------------------
    template_8 = "Navigate to the tag archive for {{tag}} and verify if the page title contains the tag name."
    for _ in range(TASKS_PER_TEMPLATE):
        tag = random.choice(unique_tags)
        # 简单的清洗
        tag = ''.join(e for e in tag if e.isalnum())
        add_task(template_8, {"tag": f"'{tag}'"})

    # ---------------------------------------------------------
    # Template 9: Author Archives (作者归档页测试)
    # "Click on the author name {{author}} on any post to view all articles written by them."
    # ---------------------------------------------------------
    # template_9 = "Click on the author name {{author}} on any post to view all articles written by them."
    # for _ in range(TASKS_PER_TEMPLATE):
    #     author = random.choice(authors)
    #     add_task(template_9, {"author": f"'{author}'"})

    # ---------------------------------------------------------
    # Template 10: Pagination (分页导航测试)
    # "Scroll to the bottom of the homepage and navigate to page {{page_num}} of the blog feed."
    # ---------------------------------------------------------
    template_10 = "Scroll to the bottom of the homepage and navigate to page {{page_num}} of the blog feed."
    # 假设博客有至少3页
    page_nums = ["2", "3", "4", "5", "6"] 
    for i in range(len(page_nums)):
        page_num = page_nums[i]
        add_task(template_10, {"page_num": page_num})

    # ---------------------------------------------------------
    # Template 11: Contact Form Interaction (非评论类表单)
    # "Navigate to the 'Contact' page and submit a message with subject {{subject}} and body {{body}}."
    # ---------------------------------------------------------
    # template_11 = "Navigate to the 'Contact' page and submit a message with subject {{subject}} and body {{body}}."
    # subjects = ["Inquiry", "Feedback", "Support Request", "Hello"]
    # bodies = [
    #     "I would like to know more about your services.", 
    #     "I found a bug on your website.", 
    #     "Just wanted to say hi!", 
    #     "Please update your contact info."
    # ]
    
    # for _ in range(TASKS_PER_TEMPLATE):
    #     subj = random.choice(subjects)
    #     body = random.choice(bodies)
    #     add_task(template_11, {
    #         "subject": f"'{subj}'",
    #         "body": f"'{body}'"
    #     })

    # ---------------------------------------------------------
    # Template 12: Content Verification (阅读理解/视觉验证)
    # "Open the article {{title}} and check if it contains an image with the alt text {{alt_text}}."
    # ---------------------------------------------------------
    # 注意：这个任务假设Agent有能力检查DOM属性。如果没有真实Alt text数据，这里用通用词模拟。
    template_12 = "Open the article {{title}} and check if it contains an image related to {{keyword}}."
    
    selected_titles_12 = random.sample(titles, min(len(titles), TASKS_PER_TEMPLATE))
    for title in selected_titles_12:
        # 简单地取标题里的一个词作为假设的图片关键词
        words = title.split()
        keyword = words[-1] if words else "image"
        add_task(template_12, {
            "title": f"'{title}'",
            "keyword": f"'{keyword}'"
        })

    # ---------------------------------------------------------
    # Template 13: Sidebar/Widget Date Navigation (归档微件)
    # "Find the 'Archives' widget and click on the link for {{month_year}}."
    # ---------------------------------------------------------
    template_13 = "Find the 'Archives' widget and click on the link for {{month_year}}."
    # 生成最近几个月的日期字符串
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    years = ["2023", "2024", "2025"]
    
    for _ in range(TASKS_PER_TEMPLATE):
        month = random.choice(months)
        year = random.choice(years)
        add_task(template_13, {"month_year": f"'{month} {year}'"})

    return tasks

def main():
    print(f"📂 Loading data from {INPUT_FILE}...")
    articles = load_data()
    
    if not articles:
        print("⚠️ No articles loaded. Generating basic templates only.")
        # 创建一些假数据防止崩溃
        articles = [{"title": "Sample Article", "category": "General"}]

    generated_tasks = generate_tasks(articles)
    
    print(f"💾 Saving {len(generated_tasks)} tasks to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(generated_tasks, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Done! Generated {len(generated_tasks)} tasks.")

if __name__ == "__main__":
    main()