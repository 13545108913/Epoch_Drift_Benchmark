import logging
import os
import time

import playwright.sync_api
import requests

logger = logging.getLogger(__name__)

# ENV_VARS = ("SHOPPING", "SHOPPING_ADMIN", "REDDIT", "GITLAB", "WIKIPEDIA", "MAP", "HOMEPAGE")


# class MyBenchmarkInstance:
#     """
#     Utility class to access MyBenchmark instance.

#     """

#     RESET_URL_VAR = "WA_FULL_RESET"  # used by full_reset()

#     def __init__(
#         self,
#     ) -> None:

#         # setup webarena environment variables (webarena will read those on import)
#         append_wa = lambda x: f"WA_{x}"
#         for key in ENV_VARS:
#             assert append_wa(key) in os.environ, (
#                 f"Environment variable {append_wa(key)} missing.\n"
#                 + "Please set the following environment variables to use WebArena through BrowserGym:\n"
#                 + "\n".join([append_wa(x) for x in ENV_VARS])
#             )
#             os.environ[key] = os.environ[append_wa(key)]

#         # import webarena on instanciation
#         from webarena.browser_env.env_config import (
#             ACCOUNTS,
#             GITLAB,
#             HOMEPAGE,
#             MAP,
#             REDDIT,
#             SHOPPING,
#             SHOPPING_ADMIN,
#             WIKIPEDIA,
#         )

#         self.urls = {
#             "reddit": REDDIT,
#             "gitlab": GITLAB,
#             "shopping": SHOPPING,
#             "shopping_admin": SHOPPING_ADMIN,
#             "wikipedia": WIKIPEDIA,
#             "map": MAP,
#         }
#         self.home_url = HOMEPAGE

#         self.credentials = ACCOUNTS

#     def full_reset(self, skip_if_not_set: bool = True):
#         base_url = os.environ.get(self.RESET_URL_VAR, None)

#         if not base_url:
#             # check for reset URL
#             logger.error(
#                 f"Environment variable {self.RESET_URL_VAR} is missing or empty, required for a full instance reset."
#             )
#             if skip_if_not_set:
#                 logger.warning(
#                     f"Skipping automated reset. Make sure the instance has been manually reset."
#                 )
#             else:
#                 raise RuntimeError(f"Could not reset instance, aborting.")

#         else:
#             # reset the instance
#             reset_url = f"{base_url}/reset"
#             status_url = f"{base_url}/status"

#             logger.info(
#                 f"Initiating {self.__class__.__name__} instance reset on URL {reset_url}. Should take between 200 - 500 seconds to restart."
#             )

#             # trigger instance reset
#             response = requests.get(reset_url)
#             match response.status_code:
#                 case 200:
#                     logger.info(f"Reset started.")
#                 case 418:
#                     logger.warning("Reset was already running.")
#                 case _:
#                     raise Exception(
#                         f"{self.__class__.__name__} reset request {reset_url} failed ({response.status_code}): {response.text}"
#                     )

#             # wait until reset complete
#             retry_after = 20  # 20 seconds wait between status checks
#             timeout = 10 * 60  # 10 minutes timeout
#             start_time = time.time()
#             while True:
#                 # request instance status
#                 response = requests.get(status_url)
#                 # check for server error
#                 if response.status_code != 200:
#                     raise Exception(
#                         f"{self.__class__.__name__} status request {status_url} failed ({response.status_code}): {response.text}"
#                     )
#                 # check for readiness
#                 if response.text == "Ready for duty!":
#                     break
#                 # check for timeout
#                 time_elapsed = time.time() - start_time
#                 logger.info(f"Reset still running after {time_elapsed:.0f} seconds...")
#                 if time_elapsed > timeout:
#                     raise Exception(
#                         f"Reset still running after {time_elapsed} seconds (> {timeout}), aborting."
#                     )
#                 # wait a bit before next retry
#                 time.sleep(retry_after)

#         # warm-start the instance (navigate to every domain)
#         retries_left = 3
#         while retries_left:
#             retries_left -= 1
#             try:
#                 self._check_is_reachable(
#                     timeout=60
#                 )  # 60 seconds, warming up after reset might be slow
#                 break
#             except Exception as e:
#                 if not retries_left:
#                     raise
#                 logger.info(
#                     f"Instance unresponsive after reset, retrying ({retries_left} retries left)\n{e}"
#                 )

#     def check_status(self):
#         """
#         Check the status of the instance. Raises an error if the instance is not ready to be used.

#         """
#         self._check_is_reachable(timeout=10)  # 10 seconds

#     def _check_is_reachable(self, timeout: int):
#         """
#         Test that every website is reachable.

#         """
#         for site, url in self.urls.items():
#             try:
#                 requests.get(url, timeout=timeout)
#             except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
#                 raise RuntimeError(
#                     f'WebArena site "{site}" ({url}) is not reacheable. Please check the URL.'
#                 )

#     def ui_login(self, site: str, page: playwright.sync_api.Page):
#         """
#         Should only be called once per site (expects user to be logged out).
#         """

#         url = self.urls[site]

#         # open a new page (tab) to perform the login
#         page = page.context.new_page()

#         match site:
#             case "reddit":
#                 username = self.credentials[site]["username"]
#                 password = self.credentials[site]["password"]

#                 page.goto(f"{url}")
#                 page.get_by_role("link", name="Log in").click()
#                 page.get_by_label("Username").fill(username)
#                 page.get_by_label("Password").fill(password)
#                 page.get_by_role("button", name="Log in").click()

#             case "gitlab":
#                 username = self.credentials[site]["username"]
#                 password = self.credentials[site]["password"]

#                 page.goto(f"{url}/users/sign_in")
#                 page.get_by_label("Username or email").fill(username)
#                 # page.get_by_label("Password").fill(password)
#                 page.locator("#user_password").fill(password)
#                 page.get_by_role("button", name="Sign in").click()

#             case "shopping":
#                 username = self.credentials[site]["username"]
#                 password = self.credentials[site]["password"]

#                 page.goto(f"{url}/customer/account/login/")
#                 page.get_by_label("Email", exact=True).fill(username)
#                 page.get_by_label("Password", exact=True).fill(password)
#                 page.get_by_role("button", name="Sign In").click()

#             case "shopping_admin":
#                 username = self.credentials[site]["username"]
#                 password = self.credentials[site]["password"]

#                 page.goto(url)
#                 page.get_by_label("Username").fill(username)
#                 page.get_by_label("Password").fill(password)
#                 page.get_by_role("button", name="Sign in").click()

#             case "wikipedia":
#                 page.goto(url)

#             case "map":
#                 page.goto(url)

#             case _:
#                 raise ValueError

#         # release login page
#         page.close()


# 定义支持的版本
AVAILABLE_VERSIONS = ["v1", "v2"] 

# 定义站点名称
SITE_NAMES = ("GITLAB",)

class MyBenchmarkInstance:
    """
    支持多版本网站的 Instance 管理器
    """

    def __init__(self) -> None:
        self.urls = {}
        self.credentials = {}
        
        # 1. 动态加载环境变量：例如 WA_GITLAB_V1, WA_GITLAB_V2
        for site in SITE_NAMES:
            self.urls[site.lower()] = {}
            for version in AVAILABLE_VERSIONS:
                # 构造环境变量名，如: WA_GITLAB_V1
                env_var_name = f"WA_{site}_{version.upper()}"
                
                assert env_var_name in os.environ, (
                    f"Environment variable {env_var_name} missing.\n"
                    f"Please set {env_var_name} to the URL of the {version} version of {site}."
                )
                
                # 存储结构: self.urls['gitlab']['v1'] = "http://localhost:8081"
                self.urls[site.lower()][version] = os.environ[env_var_name]

        # 2. 加载账号信息 (假设所有版本的账号密码是一样的，如果不一样也需要分版本加载)
        from webarena.browser_env.env_config import ACCOUNTS, HOMEPAGE
        self.credentials = ACCOUNTS
        self.home_url = HOMEPAGE

    def check_status(self):
        """检查所有版本的网站是否都可访问"""
        for site, versions in self.urls.items():
            for ver, url in versions.items():
                try:
                    requests.get(url, timeout=10)
                except Exception:
                    raise RuntimeError(f"Site {site} (version {ver}) at {url} is not reachable.")

    def ui_login(self, site: str, version: str, page: playwright.sync_api.Page):
        """
        新增 version 参数，确保登录到正确的网站版本
        """
        # 获取对应版本的 URL
        if site not in self.urls or version not in self.urls[site]:
             raise ValueError(f"Unknown site {site} or version {version}")
             
        base_url = self.urls[site][version]

        # open a new page (tab) to perform the login
        page = page.context.new_page()

        # --- 下面的逻辑只需将原本的 url 变量替换为 base_url ---
        match site:
            case "gitlab":
                username = self.credentials[site]["username"]
                password = self.credentials[site]["password"]
                
                # 使用 base_url
                page.goto(f"{base_url}/users/sign_in") 
                page.get_by_label("Username or email").fill(username)
                page.locator("#user_password").fill(password)
                page.get_by_role("button", name="Sign in").click()

            # ... (其他站点的登录逻辑同理，只需确保使用 base_url) ...
            case _:
                raise ValueError
            
        page.close()