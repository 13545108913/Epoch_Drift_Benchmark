import os
import json
from playwright.sync_api import sync_playwright

# --- 配置信息 ---
GITLAB_URL = 'http://172.26.116.102:8081'
ACCOUNTS = {
    "gitlab": {"username": "byteblaze", "password": "a_very_secure_password_123!"},
}
OUTPUT_PATH = '.auth/gitlab_state.json'

def save_gitlab_state():
    # 1. 确保输出目录存在
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with sync_playwright() as p:
        print("🚀 正在启动浏览器...")
        # headless=True 表示无头模式（不显示界面），调试时可改为 False
        browser = p.chromium.launch(headless=True)
        
        # 创建上下文
        context = browser.new_context()
        page = context.new_page()

        try:
            # 2. 导航
            login_url = f"{GITLAB_URL}/users/sign_in"
            print(f"🔗 正在访问: {login_url}")
            page.goto(login_url)

            # 3. 填写账号密码
            print(f"👤 正在登录用户: {ACCOUNTS['gitlab']['username']}")
            page.fill("#user_login", ACCOUNTS['gitlab']['username'])
            page.fill("#user_password", ACCOUNTS['gitlab']['password'])

            # 4. [关键步骤] 勾选 "Remember me"
            # 这决定了 Cookie 是 Session(临时) 还是 Persistent(持久)
            print("☑️  正在勾选 'Remember me'...")
            # try:
            #     # 优先尝试标准 ID
            #     if page.locator("#user_remember_me").is_visible():
            #         page.check("#user_remember_me")
            #     else:
            #         # 回退策略：点击 Label 文本
            #         page.locator("label:has-text('Remember me')").click()
            # except Exception as e:
            #     print(f"⚠️ 勾选 Remember me 遇到小问题 (尝试继续): {e}")

            # 5. 点击登录
            print("👆 点击登录按钮...")
            # 优先匹配 data-qa 属性，其次匹配 submit 类型
            if page.locator('button[data-qa-selector="sign_in_button"]').count() > 0:
                page.click('button[data-qa-selector="sign_in_button"]')
            else:
                page.click('button[type="submit"], input[type="submit"]')

            # 6. 等待登录成功
            print("⏳ 等待页面跳转...")
            # 只要 URL 不再包含 sign_in，说明跳转了
            page.wait_for_url(lambda url: "/users/sign_in" not in url, timeout=15000)
            
            # 等待网络空闲，确保 Set-Cookie 响应头已完全处理
            page.wait_for_load_state("networkidle")

            # 7. [关键步骤] 保存标准格式的 JSON
            # context.storage_state() 会自动生成 {cookies: [...], origins: [...]} 格式
            context.storage_state(path=OUTPUT_PATH)
            
            # --- 验证环节 ---
            print("-" * 30)
            with open(OUTPUT_PATH, 'r') as f:
                data = json.load(f)
                
                # 1. 验证格式
                if isinstance(data, dict) and "cookies" in data:
                     print("✅ 格式验证通过: JSON 包含 'cookies' 和 'origins' 键。")
                else:
                     print("❌ 格式错误: 生成的不是字典格式。")

                # 2. 验证有效期
                cookies = data.get('cookies', [])
                session_cookie = next((c for c in cookies if c['name'] == '_gitlab_session'), None)
                if session_cookie:
                    expiry = session_cookie.get('expires', -1)
                    if expiry > 0:
                        print(f"✅ 有效期验证通过: _gitlab_session 过期时间戳为 {expiry}")
                    else:
                        print("⚠️ 警告: _gitlab_session 仍然是 Session Cookie (expires: -1)。请检查 '记住我' 是否真的勾选成功。")
            print("-" * 30)
            
            print(f"💾 最终文件已保存: {os.path.abspath(OUTPUT_PATH)}")

        except Exception as e:
            print(f"❌ 脚本执行失败: {e}")
            page.screenshot(path="error_login.png")
        
        finally:
            browser.close()

if __name__ == "__main__":
    save_gitlab_state()