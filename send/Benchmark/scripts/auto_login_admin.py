from playwright.sync_api import sync_playwright

def get_magento_auth_state():
    # 输出文件路径
    auth_file_path = 'auth.json'
    
    with sync_playwright() as p:
        # 启动浏览器 (headless=False 可以让你看到操作过程，调试时很有用)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("正在导航到 Magento 后台登录页面...")
        try:
            # 1. 访问目标 URL
            page.goto("http://dockerized-magento.local/admin")

            # 2. 等待登录表单加载
            # Magento 2 Admin 默认用户名字段 ID 通常为 #username
            page.wait_for_selector("#username")

            # 3. 填写账号密码
            # 注意：Magento 2 Admin 的密码输入框 ID 通常是 #login，而不是 #password
            print("正在输入凭据...")
            page.fill("#username", "admin")
            page.fill("#login", "password123")

            # 4. 点击登录按钮
            # 登录按钮通常带有 .action-login 类
            print("点击登录...")
            button_m1 = page.get_by_role("button", name="Login")

            # 定义 M2 风格的按钮
            button_m2 = page.get_by_role("button", name="Sign in")

            # 结合两者，点击任意存在的那个
            button_m1.or_(button_m2).click(timeout=60000)

            # 5. 等待登录成功
            # 等待 URL 跳转包含 'dashboard' 或者页面标题包含 'Dashboard'
            page.wait_for_url("**/dashboard/**", timeout=30000)
            print("登录成功！")

            # 6. 保存 storage state
            context.storage_state(path=auth_file_path)
            print(f"Authentication state 已保存至: {auth_file_path}")

        except Exception as e:
            print(f"发生错误: {e}")
            # 如果是本地环境连接失败，请检查 hosts 文件或网络设置
            print("请确保当前机器可以访问 http://dockerized-magento.local/admin")

        finally:
            browser.close()

if __name__ == "__main__":
    get_magento_auth_state()