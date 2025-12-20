import json
import random
import os

# ================= 配置 =================
INPUT_FILE = 'diverse_real_world_data.json'
OUTPUT_FILE = 'benchmark_tasks.json'
TASKS_PER_TEMPLATE = 6  # 每个模版生成的任务数量
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
            "intent": intent
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
    for _ in range(TASKS_PER_TEMPLATE):
        cat = random.choice(categories)
        add_task(template_4, {"category": f"'{cat}'"})

    # ---------------------------------------------------------
    # Template 5: "Find the link to the {{element}} and click it."
    # ---------------------------------------------------------
    template_5 = "Find the link to the {{element}} and click it."
    elements = ["Next Post", "Previous Post", "Home", "About", "RSS Feed", "Comments"]
    
    for _ in range(TASKS_PER_TEMPLATE):
        element = random.choice(elements)
        add_task(template_5, {"element": f"'{element}'"})

    # ---------------------------------------------------------
    # Template 6: "Go to the {{title}} post and leave a comment saying: {{content}}."
    # ---------------------------------------------------------
    template_6 = "Go to the {{title}} post and leave a comment saying: {{content}}."
    comments = [
        "Great article!", 
        "Thanks for sharing.", 
        "Agent Report: Found it", 
        "Interesting perspective.", 
        "Could you elaborate on this?",
        "Test comment for benchmark."
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