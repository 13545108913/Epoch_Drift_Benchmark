import json
import time
import random
from playwright.sync_api import sync_playwright

# ==========================================
# 1. 清理并修复后的 DriftInjector 类
# ==========================================
import random

class DriftInjector:
    def __init__(self, seed=42):
        """
        :param seed: 随机种子，确保每次生成的干扰逻辑在浏览器端执行顺序一致。
        """
        self.seed = seed

    def _get_seeded_rng_script(self) -> str:
        """
        生成一个基于种子的伪随机数生成器 (LCG 算法) 的 JS 代码。
        替代 Math.random()，确保由 Python 指定的 seed 控制随机结果。
        """
        return f"""
            // === Deterministic RNG Setup ===
            window.__drift_seed = {self.seed};
            
            // 简单的线性同余生成器 (LCG)
            // 只要初始 seed 相同，生成的序列永远相同
            const seededRandom = () => {{
                window.__drift_seed = (window.__drift_seed * 9301 + 49297) % 233280;
                return window.__drift_seed / 233280;
            }};

            // 辅助函数：生成确定性的随机字符串 (用于替换 Math.random().toString(36))
            const seededString = () => {{
                return Math.floor(seededRandom() * 2147483648).toString(36);
            }};
        """

    def _get_visual_drift_css(self, intensity: str) -> str:
        """
        (保持不变) 根据强度生成 CSS 样式。
        """
        css_parts = []
        if intensity == "low":
            css_parts.append("body { background-color: #f9f9f9 !important; line-height: 1.6 !important; }")
            css_parts.append("a { text-decoration: underline !important; }")
        elif intensity == "medium":
            css_parts.append("body, * { font-family: 'Courier New', monospace !important; }")
            css_parts.append("button, .btn { border-radius: 0px !important; background-color: #4a90e2 !important; color: #fff !important; border: 2px solid #000 !important; }")
            css_parts.append("input { background-color: #fff8dc !important; }")
        elif intensity == "high":
            css_parts.append("* { letter-spacing: 1.5px !important; word-spacing: 2px !important; }")
            css_parts.append("div, p, span { transform: rotate(0.2deg); }") 
            css_parts.append("body { filter: contrast(120%); }")
            css_parts.append("button, .btn { border: 3px dashed red !important; font-weight: bold !important; }")
            
        return " ".join(css_parts).replace("\n", " ")

    def _get_mutation_params(self, intensity: str) -> dict:
        """
        (保持不变) 根据强度定义 DOM 变异的概率参数
        """
        if intensity == "low":
            return {"remove_testid_prob": 0.1, "add_class_prob": 0.2, "enable_tag_replace": False, "attr_noise_prob": 0.1}
        elif intensity == "medium":
            return {"remove_testid_prob": 0.4, "add_class_prob": 0.5, "enable_tag_replace": True, "attr_noise_prob": 0.3}
        elif intensity == "high":
            return {"remove_testid_prob": 0.8, "add_class_prob": 0.9, "enable_tag_replace": True, "attr_noise_prob": 0.6}
        return self._get_mutation_params("medium")

    def generate_drift_script(self, drift_type: str, intensity: str) -> str:
        """
        生成带有强度控制且【结果确定】的 JS 注入脚本。
        """
        params = self._get_mutation_params(intensity)
        script_parts = []
        
        # 1. 注入 RNG 核心逻辑 (这是实现“每次结果相同”的关键)
        script_parts.append(self._get_seeded_rng_script())
        
        script_parts.append(f"console.log('[DriftInjector] Intensity: {intensity}, Type: {drift_type}, Seed: {self.seed}');")

        # === Part 1: Visual Drift (CSS) ===
        if "visual" in drift_type or drift_type == "all":
            css_content = self._get_visual_drift_css(intensity)
            script_parts.append(f"""
                const injectStyles = () => {{
                    if (document.getElementById('drift-style-injected')) return;
                    const style = document.createElement('style');
                    style.textContent = "{css_content}";
                    style.id = 'drift-style-injected';
                    (document.head || document.documentElement).appendChild(style);
                }};
            """)
        else:
            script_parts.append("const injectStyles = () => {};")

        # === Part 2: DOM Mutation Logic ===
        # 注意：这里所有的 Math.random() 都被替换为了 seededRandom()
        mutation_logic = ""
        
        if "locator" in drift_type or drift_type == "all":
            mutation_logic += f"""
                // 1. 干扰 data-testid
                if (node.getAttribute && node.getAttribute('data-testid')) {{
                    if (!node.getAttribute('data-drifted-id')) {{
                        const r = seededRandom(); // <--- 使用确定性随机数
                        if (r < {params['remove_testid_prob']}) {{
                            node.removeAttribute('data-testid');
                        }} else if (r < {params['remove_testid_prob']} + {params['attr_noise_prob']}) {{
                            node.setAttribute('data-testid', node.getAttribute('data-testid') + '__drifted');
                        }}
                        node.setAttribute('data-drifted-id', 'true'); 
                    }}
                }}

                // 2. 干扰 Class
                if (node.classList && !node.classList.contains('drift-c')) {{
                    if (seededRandom() < {params['add_class_prob']}) {{ // <--- 使用确定性随机数
                        // 生成确定性的随机字符串
                        node.classList.add('drift-' + seededString()); 
                        node.classList.add('drift-c');
                    }}
                }}
            """

        if ("structural" in drift_type or drift_type == "all") and params['enable_tag_replace']:
            mutation_logic += """
                const tagMap = { 'B': 'STRONG', 'I': 'EM', 'SPAN': 'LABEL' };
                if (tagMap[node.tagName] && !node.getAttribute('data-drifted-tag')) {
                     if (node.children.length === 0 && node.textContent.length < 50) {
                        const newTag = tagMap[node.tagName];
                        const newEl = document.createElement(newTag);
                        newEl.innerHTML = node.innerHTML;
                        newEl.className = node.className;
                        newEl.setAttribute('data-drifted-tag', 'true');
                        try {
                            node.parentNode.replaceChild(newEl, node);
                        } catch(e) {}
                     }
                }
            """

        # === Part 3: Execution & Observer ===
        script_parts.append(f"""
            const applyDrift = (node) => {{
                if (!node || node.nodeType !== 1) return;
                try {{
                    {mutation_logic}
                }} catch (e) {{}}
            }};

            const startObserver = () => {{
                const target = document.body || document.documentElement;
                if (!target) {{
                    requestAnimationFrame(startObserver);
                    return;
                }}
                injectStyles();
                document.querySelectorAll('*').forEach(applyDrift);
                const observer = new MutationObserver((mutations) => {{
                    mutations.forEach((mutation) => {{
                        mutation.addedNodes.forEach((node) => {{
                            if (node.nodeType === 1) {{
                                applyDrift(node);
                                node.querySelectorAll('*').forEach(applyDrift);
                            }}
                        }});
                    }});
                }});
                observer.observe(target, {{ childList: true, subtree: true }});
            }};

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', startObserver);
            }} else {{
                startObserver();
            }}
        """)

        return "\n".join(script_parts)

# ==========================================
# 2. 执行逻辑 (含自动登录)
# ==========================================
def save_file(filename, content):
    """保存内容到文件"""
    mode = 'w'
    if isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2, ensure_ascii=False)
    
    try:
        with open(filename, mode, encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 文件已保存: {filename}")
    except Exception as e:
        print(f"❌ 保存文件 {filename} 失败: {e}")

def run_experiment():
    # --- 配置信息 ---
    target_url = "http://dockerized-magento.local/index.php/admin"
    username = "admin"
    password = "password123"
    
    seed = 12345
    intensity = "medium" 
    drift_type = "all" 

    print(f"🚀 启动 Playwright... 目标: {target_url}")

    with sync_playwright() as p:
        # headless=False 方便观察登录和注入过程
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            # 1. 打开登录页面
            print("➡️  正在访问登录页面...")
            page.goto(target_url)

            # 2. 执行登录
            # 检查是否在登录页 (通过查找 username 输入框)
            if page.locator("#username").count() > 0:
                print(f"🔑 检测到登录页，正在登录用户: {username}")
                
                # Magento Admin 标准选择器
                page.fill("#username", username)
                page.fill("#login", password) # Magento 2 密码框 id 通常是 "login"
                
                # 点击登录按钮
                button_m1 = page.get_by_role("button", name="Login")

                # 定义 M2 风格的按钮
                button_m2 = page.get_by_role("button", name="Sign in")

                # 结合两者，点击任意存在的那个
                button_m1.or_(button_m2).click(timeout=60000)
                
                # 等待页面加载完成 (等待 Dashboard 出现)
                page.wait_for_load_state("networkidle")
                print("🎉 登录成功 (Network Idle)")
            else:
                print("⚠️  未检测到登录框，可能已经登录或页面结构不同。")

            # 3. 注入前：保存基准状态 (Baseline)
            print("\n📸 [Pre-Drift] 正在捕获注入前状态...")
            # 确保稍微等待一下，以防 Dashboard 的 JS 还在渲染
            time.sleep(3) 
            
            pre_html = page.content()
            pre_axtree = page.accessibility.snapshot()
            
            save_file("1_pre_drift.html", pre_html)
            save_file("1_pre_drift_axtree.json", pre_axtree)

            # 4. 注入 Drift 脚本
            print(f"\n💉 [Injection] 正在注入 Drift 脚本 (Mode: {drift_type}, Intensity: {intensity})...")
            injector = DriftInjector(seed=seed)
            js_code = injector.generate_drift_script(drift_type, intensity)
            
            page.evaluate(js_code)
            
            # 等待 MutationObserver 和样式生效
            time.sleep(3)

            # 5. 注入后：保存偏移状态 (Drifted)
            print("\n📸 [Post-Drift] 正在捕获注入后状态...")
            post_html = page.content()
            post_axtree = page.accessibility.snapshot()

            save_file("2_post_drift.html", post_html)
            save_file("2_post_drift_axtree.json", post_axtree)

            print("\n✨ 所有任务完成。")

        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            # 截图保存错误现场
            try:
                page.screenshot(path="error_screenshot.png")
                print("🖼️  已保存错误截图: error_screenshot.png")
            except:
                pass
        finally:
            browser.close()

if __name__ == "__main__":
    run_experiment()
