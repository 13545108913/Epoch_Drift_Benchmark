import os
from playwright.sync_api import sync_playwright

def save_magento_auth():
    auth_dir = ".auth"
    auth_file = "shopping_admin_state.json"
    auth_path = os.path.join(auth_dir, auth_file)
    
    # 确保这里的域名已经在 /etc/hosts 做了解析
    target_url = "http://localhost:7780/admin/admin/"
    
    # 【注意】请确保这里填的是当前数据库里实际生效的密码
    username = "admin" 
    password = "admin1234" 

    if not os.path.exists(auth_dir):
        os.makedirs(auth_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        
        # 优化：忽略 HTTPS 证书错误，防止因本地自签名证书导致脚本中断
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        print(f"正在访问: {target_url}")
        try:
            page.goto(target_url)

            print("正在输入凭据...")
            # 等待用户名输入框出现
            page.wait_for_selector("#username", state="visible")
            page.fill("#username", username)
            
            # Magento 1.9 密码框 ID 通常是 "login"，但也可能是 name="login[password]"
            # 这里做一个兼容处理，如果找不到 ID，就尝试找 name
            if page.query_selector("#login"):
                page.fill("#login", password)
            else:
                page.fill("input[name='login[password]']", password)
            
            # 点击登录
            # page.click("input[type='submit']")

            button_m1 = page.get_by_role("button", name="Login")

            # 定义 M2 风格的按钮
            button_m2 = page.get_by_role("button", name="Sign in")

            # 结合两者，点击任意存在的那个
            button_m1.or_(button_m2).click(timeout=60000)

            
            print("正在等待登录跳转...")
            # 增加超时时间到 30秒，防止本地环境慢
            page.wait_for_url("**/admin/dashboard/**", timeout=30000)
            print("登录成功！")

            context.storage_state(path=auth_path)
            print(f"认证状态已保存至: {auth_path}")

        except Exception as e:
            print(f"发生错误: {e}")
            page.screenshot(path="error_screenshot.png")
            # 如果是超时，打印一下当前 URL 看看停在哪里了
            print(f"当前停留页面: {page.url}")

        finally:
            browser.close()

if __name__ == "__main__":
    save_magento_auth()