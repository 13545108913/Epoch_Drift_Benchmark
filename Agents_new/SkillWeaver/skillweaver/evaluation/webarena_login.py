"""Script to automatically login each website"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
import requests

from skillweaver.evaluation.webarena_config import ACCOUNTS
from skillweaver.environment import make_browser
from playwright.async_api import async_playwright

HEADLESS = True
SLOW_MO = 0
SHOPPING_ADMIN = "ec2-18-118-35-60.us-east-2.compute.amazonaws.com:7780/admin"


# We can do this cheaply on WebArena. May want to improve for live websites.
# `comb` is a dictionary of website name -> host.
# example `comb``: {"shopping": "127.0.0.1:8003"}
async def webarena_renew_comb(comb: dict[str, str], path: str):
    comb = {k: v[7:] if v.startswith("http://") else v for k, v in comb.items()}

    # --- 新增代码开始：发送停止干扰信号 ---
    # stop_url = "http://dockerized-magento.local/admin/?logging=EndingMyTest"
    
    # # 必须配置代理，指向你的 mitmproxy (通常是 8848 端口)
    # # 这样 addon 脚本才能捕获到这个请求并重置状态
    # mitm_proxy = "http://127.0.0.1:8848" 
    # proxies = {
    #     "http": mitm_proxy,
    #     "https": mitm_proxy,
    # }

    # try:
    #     # 发送请求，设置超时防止卡死
    #     response = requests.get(stop_url, proxies=proxies, timeout=20)
    #     print(f"OK: Connect to {stop_url}")
    # except requests.exceptions.ProxyError:
    #     print("Error: Could not connect to mitmproxy on port 8848. Is it running?")
    # except Exception as e:
    #     print(f"Failed to send stop signal: {e}")
    # --- 新增代码结束 ---

    # Returns the filename.
    async with async_playwright() as p:
        browser = await make_browser(
            p,
            "http://" + list(comb.values())[0],
            headless=HEADLESS,
            navigation_timeout=30000,
            timeout=30000,
        )
        page = browser.active_page

        for key, host in comb.items():
            if key == "shopping":
                username = ACCOUNTS["shopping"]["username"]
                password = ACCOUNTS["shopping"]["password"]
                print(f"Logging into {key} at {host}")
                print(f"user: {username}, pass: {password}")
                await page.goto(f"http://{host}/customer/account/login/")
                await page.get_by_label("Email", exact=True).fill(username)
                await page.get_by_label("Password", exact=True).fill(password)
                await page.get_by_role("button", name="Sign In").click()
                # Wait for the request to finish.
                await page.wait_for_load_state("networkidle")

            if key == "reddit":
                username = ACCOUNTS["reddit"]["username"]
                password = ACCOUNTS["reddit"]["password"]
                print(f"Logging into {key} at {host}")
                print(f"user: {username}, pass: {password}")
                await page.goto(f"http://{host}/login")
                await page.get_by_label("Username").fill(username)
                await page.get_by_label("Password").fill(password)
                await page.get_by_role("button", name="Log in").click()
                # Wait for the request to finish.
                await page.wait_for_load_state("networkidle")

            if key == "shopping_admin":
                username = ACCOUNTS["shopping_admin"]["username"]
                password = ACCOUNTS["shopping_admin"]["password"]
                print(f"Logging into {key} at {host}")
                print(f"user: {username}, pass: {password}")
                await page.goto(f"http://{host}")
                # await page.get_by_placeholder("user name").fill(username)
                # await page.get_by_placeholder("password").fill(password)
                # await page.get_by_role("button", name="Sign in").click()
                # 1. 输入用户名
                await page.locator("#username").fill(username)

                # 2. 输入密码 (HTML中 id="login")
                await page.locator("#login").fill(password)

                # 3. 点击登录按钮
                # 定义 M1 风格的按钮 (get_by_role 不需要 await)
                button_m1 = page.get_by_role("button", name="Login")

                # 定义 M2 风格的按钮 (get_by_role 不需要 await)
                button_m2 = page.get_by_role("button", name="Sign in")

                # 结合两者，点击任意存在的那个 (click 需要 await)
                await button_m1.or_(button_m2).click(timeout=60000)
                # Wait for the request to finish.
                await page.wait_for_load_state("networkidle")

                await page.goto("http://dockerized-magento.local/admin/?logging=StartingRun1")
                await page.goto("http://dockerized-magento.local/admin/")

            if key == "gitlab":
                username = ACCOUNTS["gitlab"]["username"]
                password = ACCOUNTS["gitlab"]["password"]
                print(f"Logging into {key} at {host}")
                print(f"user: {username}, pass: {password}")
                await page.goto(f"http://{host}/users/sign_in")

                # await page.get_by_test_id("username-field").click()
                # await page.get_by_test_id("username-field").fill(username)
                # await page.get_by_test_id("username-field").press("Tab")
                # await page.get_by_test_id("password-field").fill(password)
                # await page.get_by_test_id("sign-in-button").click()
                # # Wait for the request to finish.
                # # await page.wait_for_load_state("load")
                # await asyncio.sleep(5)

                # ----------------------------------------------------
                # START: 关键修改部分 - 解决严格模式冲突
                # ----------------------------------------------------
                
                # 1. 用户名输入框：使用 get_by_label("Username or Email") 或 name="user[login]"
                #    这里我们沿用上一次修改的逻辑
                username_locator = page.get_by_label("Username or Email") 
                if not await username_locator.is_visible():
                    # Fallback to precise name attribute locator
                    username_locator = page.locator('input[name="user[login]"]') 
                    
                await username_locator.click() # 点击以聚焦
                await username_locator.fill(username)
                await username_locator.press("Tab") # 按 Tab 键跳转
                
                # 2. 密码输入框：【主要修改点】
                #    使用更精确的 CSS 选择器：只选择 name="user[password]" 的 <input> 元素。
                password_locator = page.locator('input[name="user[password]"]')
                    
                # 我们不再需要 is_visible() 检查，因为我们已经使用了最准确的定位符。
                # 只需要确保元素可见即可进行后续操作。
                await password_locator.fill(password)
                
                # 3. 登录按钮：使用 get_by_role("button", name="Sign in")
                await page.get_by_role("button", name="Sign in").click()
                
                # ----------------------------------------------------
                # END: 关键修改部分
                # ----------------------------------------------------
                await page.goto("http://172.26.116.102:8081/?logging=StartingRun1")
                await page.goto("http://172.26.116.102:8081")
                await asyncio.sleep(8)

        await browser.context.storage_state(path=path)
        await browser.close()

    os._exit(0)


def login_subprocess(comb: dict[str, str]):
    auth_dir = os.path.dirname(__file__) + "/.auth"
    if not os.path.exists(auth_dir):
        os.makedirs(auth_dir)
    auth_path = os.path.abspath(f"{auth_dir}/{uuid.uuid4().hex}.json")
    print("=====auth_path", auth_path)

    command = [
        "python",
        "-m",
        "skillweaver.evaluation.webarena_login",
        json.dumps({"comb": comb, "path": auth_path}),
    ]
    print("=====command", command)
    subprocess.run(command)
    if not os.path.exists(auth_path):
        return None
    else:
        return auth_path


async def login_subprocess_async(comb: dict[str, str]):
    from asyncio.subprocess import create_subprocess_exec

    auth_dir = os.path.dirname(__file__) + "/.auth"
    if not os.path.exists(auth_dir):
        os.makedirs(auth_dir)
    auth_path = os.path.abspath(f"{auth_dir}/{uuid.uuid4().hex}.json")
    proc = await create_subprocess_exec(
        "python",
        "-m",
        "skillweaver.evaluation.webarena_login",
        json.dumps({"comb": comb, "path": auth_path}),
    )
    await proc.communicate()
    if not os.path.exists(auth_path):
        return None
    else:
        return auth_path


async def test_shopping_admin():
    """Test function for shopping_admin login"""
    comb = {"shopping_admin": SHOPPING_ADMIN}
    auth_dir = os.path.dirname(__file__) + "/.auth"
    if not os.path.exists(auth_dir):
        os.makedirs(auth_dir)
    auth_path = os.path.abspath(f"{auth_dir}/{uuid.uuid4().hex}.json")

    print(f"Starting shopping_admin login test...")
    print(f"Testing URL: {SHOPPING_ADMIN}")
    await webarena_renew_comb(comb, auth_path)


if __name__ == "__main__":
    # asyncio.run(test_shopping_admin())
    data = json.loads(sys.argv[1])
    asyncio.run(webarena_renew_comb(data["comb"], data["path"]))
