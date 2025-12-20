import os
from playwright.sync_api import sync_playwright

def save_magento_auth():
    # 1. 定义目标路径和凭据
    auth_dir = ".auth"
    auth_file = "shopping_admin_state.json"
    auth_path = os.path.join(auth_dir, auth_file)
    
    target_url = "http://dockerized-magento.local/index.php/admin/"
    username = "admin"
    password = "password123"

    # 确保输出目录存在
    if not os.path.exists(auth_dir):
        os.makedirs(auth_dir)

    with sync_playwright() as p:
        # 2. 启动浏览器 (headless=False 可以让你看到登录过程，方便调试)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"正在访问: {target_url}")
        page.goto(target_url)

        # 3. 填写登录表单
        # Magento 1.9 后台通常使用 id="username" 和 id="login" (或 name="login[password]")
        # 如果你的主题不同，可能需要根据实际页面调整选择器
        try:
            print("正在输入凭据...")
            page.wait_for_selector("#username", state="visible")
            page.fill("#username", username)
            page.fill("#login", password)
            
            # 点击登录按钮 (通常是 input type='submit' 或 class='form-button')
            page.click("input[type='submit']")
            
            # 4. 等待登录成功
            # 我们等待 URL 包含 'dashboard' 或者特定的 Dashboard 元素出现
            print("正在等待登录跳转...")
            page.wait_for_url("**/admin/dashboard/**", timeout=15000)
            print("登录成功！")

            # 5. 保存状态到 JSON 文件
            context.storage_state(path=auth_path)
            print(f"认证状态已保存至: {auth_path}")

        except Exception as e:
            print(f"发生错误: {e}")
            # 截图以便调试
            page.screenshot(path="error_screenshot.png")
            print("已保存错误截图至 error_screenshot.png")

        finally:
            browser.close()

if __name__ == "__main__":
    save_magento_auth()