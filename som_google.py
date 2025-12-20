from playwright.sync_api import sync_playwright
import time
import requests
from Benchmark.drift import DriftInjector

def run():
    # 启动 Playwright
    with sync_playwright() as p:

        # --- 新增代码开始：发送停止干扰信号 ---
        stop_url = "http://172.26.116.102:8080/?logging=StartingRun1"
        
        # 必须配置代理，指向你的 mitmproxy (通常是 8848 端口)
        # 这样 addon 脚本才能捕获到这个请求并重置状态
        mitm_proxy = "http://127.0.0.1:8848" 
        proxies = {
            "http": mitm_proxy,
            "https": mitm_proxy,
        }

        try:
            # 发送请求，设置超时防止卡死
            response = requests.get(stop_url, proxies=proxies, timeout=5)
        except requests.exceptions.ProxyError:
            print("Error: Could not connect to mitmproxy on port 8848. Is it running?")
        except Exception as e:
            print(f"Failed to send stop signal: {e}")
        # --- 新增代码结束 ---
        # 使用有头模式 (headless=False) 以便肉眼观察效果
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        
        
        # 创建上下文，设置较大的视口以便观察
        context = browser.new_context(no_viewport=True)

        # ==========================================
        # 核心：注入反爬虫模拟脚本 (JavaScript)
        # ==========================================
        anti_scraping_js = """
        // 立即执行函数，避免污染全局变量
        (function() {
            console.log("【反爬模拟系统】核心脚本已注入...");

            // --- 定义：显示真实感验证码 DOM 的函数 ---
            function showRealisticCaptcha() {
                // 防止重复弹出
                if (document.getElementById('mock-captcha-overlay')) return;

                console.log("【反爬模拟系统】检测到关键操作，触发验证码拦截。");

                // 1. 创建全屏半透明遮罩层
                const overlay = document.createElement('div');
                overlay.id = 'mock-captcha-overlay';
                // 使用 CSS text 设置样式，确保层级最高，阻挡底部操作
                overlay.style.cssText = `
                    position: fixed;
                    top: 0; left: 0; width: 100vw; height: 100vh;
                    background-color: rgba(0, 0, 0, 0.6); /* 半透明黑色背景 */
                    z-index: 2147483647; /* 浏览器允许的最大 z-index */
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    backdrop-filter: blur(4px); /* 背景模糊效果，增加真实感 */
                `;

                // 2. 创建验证码对话框容器
                const container = document.createElement('div');
                container.style.cssText = `
                    background: #ffffff;
                    width: 400px;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
                    text-align: center;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    animation: popIn 0.3s ease-out;
                `;

                // 添加一个简单的弹出动画 CSS
                const styleTag = document.createElement('style');
                styleTag.innerHTML = `@keyframes popIn { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }`;
                document.head.appendChild(styleTag);

                // 3. 填充对话框内容 HTML
                container.innerHTML = `
                    <h3 style="margin: 0 0 15px; color: #333; font-size: 22px;">🛡️ 安全检查</h3>
                    <p style="color: #666; font-size: 14px; margin-bottom: 25px;">
                        系统检测到您的操作过于频繁，为保障账号安全，请完成下方验证。
                    </p>
                    
                    <div style="background: #f0f2f5; border: 2px dashed #d0d7de; border-radius: 8px; padding: 30px 20px; margin-bottom: 25px;">
                        <div style="color: #888; font-style: italic; font-size: 16px;">
                            [ 🤖 此处模拟复杂的图形/滑动验证码 ]
                        </div>
                        <div style="margin-top: 10px; font-size: 12px; color: #aaa;">(请想象这里有一个需要拖动的滑块)</div>
                    </div>

                    <button id="mock-verify-btn" style="
                        background-color: #1a73e8;
                        color: white;
                        border: none;
                        padding: 12px 40px;
                        font-size: 16px;
                        font-weight: 600;
                        border-radius: 6px;
                        cursor: pointer;
                        transition: background-color 0.2s;
                        width: 100%;
                    ">
                        点击完成验证 (模拟通过)
                    </button>
                    <div style="margin-top: 15px; font-size: 12px; color: #999; cursor: pointer;">遇到问题？联系客服</div>
                `;

                // 4. 组装 DOM
                overlay.appendChild(container);
                document.body.appendChild(overlay);

                // 5. 绑定验证按钮点击事件 (模拟验证成功)
                document.getElementById('mock-verify-btn').onclick = function() {
                    // 移除遮罩层
                    document.body.removeChild(overlay);
                    console.log("【反爬模拟系统】验证通过。");
                    // 可选：提示用户重新操作
                    // alert("✅ 验证通过！请重新点击提交按钮。");
                };

                // 按钮悬停效果
                const btn = document.getElementById('mock-verify-btn');
                btn.onmouseover = () => btn.style.backgroundColor = '#155dbd';
                btn.onmouseout = () => btn.style.backgroundColor = '#1a73e8';
            }


            // --- 主逻辑：在捕获阶段监听全局点击 ---
            // 使用 'true' 开启捕获模式，确保在 GitLab Vue 事件之前拦截
            document.addEventListener('click', function(event) {
                let target = event.target;
                
                // 向上寻找关键元素 (应对点击到图标的情况)
                // 寻找提交按钮 (通常在 form 里的 button 或 input type=submit)
                // GitLab 的提交按钮有时 class 比较深，这里尝试匹配常见的特征
                let submitBtn = target.closest('button[type="submit"], input[type="submit"], .qa-issuable-create-button, .btn-confirm');
                
                // 寻找搜索区域 (顶部搜索框或搜索按钮)
                let searchArea = target.closest('input[type="search"], .search-input-container, header .search-form');


                // --- 场景 1: 拦截提交操作 -> 弹出验证码 DOM ---
                if (submitBtn) {
                    console.log("拦截到提交按钮点击:", submitBtn);
                    // 核心：阻止事件传播和默认行为
                    event.preventDefault();
                    event.stopPropagation();
                    // event.stopImmediatePropagation(); // 确保阻止同一元素上的其他监听器
                    
                    // 调用函数显示 DOM
                    showRealisticCaptcha();
                    return;
                }

                // --- 场景 2: 拦截搜索操作 -> 强制跳转 ---
                if (searchArea) {
                    console.log("拦截到搜索操作:", searchArea);
                    event.preventDefault();
                    event.stopPropagation();
                    
                    // 模拟未登录跳转
                    console.log("【反爬模拟系统】搜索需要登录，正在跳转...");
                    // 这里假设 GitLab 的登录路径是 /users/sign_in，请根据实际情况调整
                    window.location.href = "/users/sign_in?redirect_to=" + encodeURIComponent(window.location.pathname);
                    return;
                }

            }, true); // <--- 'true' 是关键！

        })();
        """
        # ==========================================
        # 注入脚本结束
        # ==========================================

        # 1. 生成漂移脚本 (此时还没加载页面)
        injector = DriftInjector()
        drift_script = injector.generate_drift_script(
            drift_type='all',
            intensity='high'
        )

        # 2. === 关键修改 ===
        # 将脚本添加到 Context 级别
        # 这确保了后续所有的 Navigation (跳转) 都会自动执行这段脚本
        # context.add_init_script(drift_script)

        # 【强烈建议】检查 BrowserGym 或 WebArena 的环境初始化代码
        # 确保 BrowserContext 创建时设置了 ignore_https_errors=True 和 bypass_csp=True
        # 如果你无法控制 Context 创建，可以尝试通过 CDP Session 强制禁用 CSP：


        # 将脚本添加到上下文中
        # context.add_init_script(anti_scraping_js)

        # 创建页面并访问
        page = context.new_page()
        
        try:
            print("正在载入你的 GitLab 网站...")
            # 【重要】请替换为你自己的 GitLab 地址
            # 建议访问一个具体的项目页面以便测试提交，例如:
            # page.goto("https://your-gitlab-domain.com/root/my-project/-/issues/new") 
            # 演示用，访问 GitLab 官方的 Explore 页面
            page.goto("http://172.26.116.102:8080") 
            print("页面加载完成。")

            print("\n" + "="*40)
            print(" 测试指南:")
            print(" 1. 【测试搜索拦截】")
            print("    点击顶部导航栏的“搜索”输入框，应该会立即跳转到登录页。")
            print("\n 2. 【测试验证码 DOM】")
            print("    请导航到任意一个可以提交表单的地方（例如：创建 Issue、创建 Snippet、编辑文件提交）。")
            print("    点击“Submit issue”或“Commit changes”按钮，应该会弹出一个全屏的模拟验证码遮罩层。")
            print("    点击遮罩层中的蓝色按钮可关闭它。")
            print("="*40 + "\n")
            
            # 暂停脚本，保持浏览器开启，等待手动操作测试
            page.pause()

        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()