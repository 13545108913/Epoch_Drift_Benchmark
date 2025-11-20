import asyncio
import os
from playwright.async_api import async_playwright

# --- 配置 ---
# 确保这是你 GitLab 实例的登录页面
LOGIN_URL = 'http://localhost:8080/users/sign_in' 

# 这是我们希望生成的文件路径
OUTPUT_FILE = '.auth/gitlab_state.json'
# ---

async def main():
    # 确保 .auth 目录存在
    output_dir = os.path.dirname(OUTPUT_FILE)
    if output_dir and not os.path.exists(output_dir):
        print(f"正在创建目录: {output_dir}")
        os.makedirs(output_dir)

    async with async_playwright() as p:
        print("正在启动 Chromium 浏览器...")
        
        # 启动一个 "headed" (非无头) 浏览器，这样你才能看到界面
        # 我们在这里不使用持久化上下文，因为我们希望是一个干净的开始
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"正在导航到登录页面: {LOGIN_URL}")
        await page.goto(LOGIN_URL)

        # --- 人工交互部分 ---
        print("\n" + "="*50)
        print(">>> 需要您操作 <<<")
        print("一个浏览器窗口已经打开。")
        print("请在该窗口中手动登录您的 GitLab 帐户 (例如 'root')。")
        print("当您 **成功** 登录并看到 GitLab 仪表盘后,")
        print("请返回此终端窗口，然后按 [Enter] 键。")
        print("="*50 + "\n")
        
        input("登录成功后，请在此处按 [Enter] 键...")
        # --- 交互结束 ---

        print("收到确认。正在保存身份验证状态...")

        # 将浏览器的状态 (cookies, local storage 等) 保存到文件
        # 这就是生成 storage_state 的核心
        await context.storage_state(path=OUTPUT_FILE)

        await browser.close()
        print(f"\n操作成功！")
        print(f"身份验证状态已保存到: {OUTPUT_FILE}")
        print("您现在可以运行 'check_urls_authenticated.py' 脚本了。")

if __name__ == "__main__":
    print("提示：此脚本将打开一个浏览器窗口，需要您手动登录。")
    print("请确保您已安装 Playwright ('pip install playwright') 及其浏览器 ('playwright install')。")
    asyncio.run(main())