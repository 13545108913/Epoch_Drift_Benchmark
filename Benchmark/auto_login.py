import os
from playwright.sync_api import sync_playwright

# --- 配置信息 ---
GITLAB_URL = 'http://172.26.116.102:8080'
ACCOUNTS = {
    "gitlab": {"username": "byteblaze", "password": "a_very_secure_password_123!"},
}
OUTPUT_PATH = '.auth/gitlab_state.json'

def save_gitlab_state():
    # 1. 确保输出目录存在
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with sync_playwright() as p:
        print("正在启动浏览器...")
        # 如果需要看到登录过程，可以将 headless 设置为 False
        browser = p.chromium.launch(headless=True)
        
        # 创建上下文 (Context)
        context = browser.new_context()
        page = context.new_page()

        try:
            # 2. 导航到登录页面
            login_url = f"{GITLAB_URL}/users/sign_in"
            print(f"正在访问: {login_url}")
            page.goto(login_url)

            # 3. 填写凭据
            # GitLab 通常使用 id="user_login" 和 id="user_password"
            print(f"正在登录用户: {ACCOUNTS['gitlab']['username']}")
            page.fill("#user_login", ACCOUNTS['gitlab']['username'])
            page.fill("#user_password", ACCOUNTS['gitlab']['password'])

            # 4. 点击登录
            # 尝试定位标准的登录按钮
            # 也可以使用 'button[type="submit"]' 或 'input[type="submit"]'
            if page.locator('button[data-qa-selector="sign_in_button"]').count() > 0:
                page.click('button[data-qa-selector="sign_in_button"]')
            else:
                # 回退方案：点击任何提交类型的按钮或含有"Sign in"文字的按钮
                page.click('button[type="submit"], input[type="submit"]')

            # 5. 等待登录完成
            # 等待 URL 跳转到非登录页面，或等待某个登录后才有的元素出现
            print("等待跳转...")
            page.wait_for_url(lambda url: "/users/sign_in" not in url, timeout=10000)
            
            # 也可以等待用户菜单出现来确认登录成功 (可选)
            # page.wait_for_selector('.header-user-dropdown-toggle') 

            # 6. 保存状态到 JSON 文件
            context.storage_state(path=OUTPUT_PATH)
            print(f"✅ 成功！登录状态已保存至: {os.path.abspath(OUTPUT_PATH)}")

        except Exception as e:
            print(f"❌ 发生错误: {e}")
            # 截图以便调试
            page.screenshot(path="error_screenshot.png")
            print("已保存错误截图至 error_screenshot.png")
        
        finally:
            browser.close()

if __name__ == "__main__":
    save_gitlab_state()