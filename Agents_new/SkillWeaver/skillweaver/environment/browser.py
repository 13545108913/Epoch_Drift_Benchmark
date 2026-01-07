import asyncio
import os
import time
import uuid
from tempfile import TemporaryDirectory

import PIL.Image
from aioconsole import aprint
from playwright.async_api import Browser as PlaywrightBrowser
from playwright.async_api import BrowserContext, Page, Playwright

from skillweaver.environment.a11y import capture_accessibility_tree
from skillweaver.environment.state import State

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"


def unique_id():
    return uuid.uuid4().hex


scount = 0


class Browser:
    def __init__(
        self,
        playwright_browser: PlaywrightBrowser,
        context: BrowserContext,
        active_page: Page,
        screen_size: tuple[int, int],
    ):
        """
        Use the `make_browser` helper method instead.
        """

        self.playwright_browser = playwright_browser
        self.context = context
        self.active_page = active_page
        self.temp_dir = TemporaryDirectory()
        self.dialog = None
        self.cdp_sessions = {}
        self.screen_size = screen_size

    async def _get_dom(self, page: Page):
        if page not in self.cdp_sessions:
            cdp = await self.context.new_cdp_session(page)
            self.cdp_sessions[page] = cdp
        else:
            cdp = self.cdp_sessions[page]
        dom_snapshot = await cdp.send(
            "DOMSnapshot.captureSnapshot",
            {
                "computedStyles": ["visibility", "display"],
                # Provides clientRect, scrollRect, etc.
                "includeDOMRects": True,
            },  # type: ignore (DOMSnapshot)
        )
        return dom_snapshot

    async def _screenshot(self, page: Page) -> tuple[PIL.Image.Image, PIL.Image.Image]:
        global scount
        assert (
            self.dialog is None
        ), "Cannot take any action while a dialog is open (action: screenshot)."

        # Returns the full and cropped screenshot paths
        scount += 1
        screenshot_path_full = os.path.join(
            self.temp_dir.name, f"screenshot_full{scount}.png"
        )
        screenshot_path = os.path.join(self.temp_dir.name, f"screenshot{scount}.png")
        await page.screenshot(full_page=True, path=screenshot_path_full, timeout=15000)
        await page.screenshot(full_page=False, path=screenshot_path, timeout=15000)
        screenshot = PIL.Image.open(screenshot_path)
        screenshot_full = PIL.Image.open(screenshot_path_full)

        os.remove(screenshot_path_full)
        os.remove(screenshot_path)

        return (screenshot, screenshot_full)

    async def _observe(self) -> State:
        await self.active_page.wait_for_load_state("load")
        return State(
            id=unique_id(),
            url=self.active_page.url,
            title=await self.active_page.title(),
            timestamp=time.time(),
            screenshot=(await self._screenshot(self.active_page))[0],  # BUG
            dom=await self._get_dom(self.active_page),
            dialog=self.dialog,
            accessibility_tree=await capture_accessibility_tree(self.active_page),
        )

    async def observe(self) -> State:
        exc = None
        for attempt in range(3):
            try:
                return await self._observe()
            except Exception as e:
                if (
                    "Execution context was destroyed, most likely because of a navigation"
                    in str(e)
                    and attempt < 2
                ):
                    await aprint("Page navigated after action completed. Retrying.")
                    await asyncio.sleep(2)
                    exc = e
                    continue
                else:
                    raise e

        raise exc  # type: ignore

    async def close(self):
        await self.active_page.close()
        await self.context.close()
        await self.playwright_browser.close()


async def make_browser(
    playwright: Playwright,
    start_url: str,
    storage_state: str | None = None,
    headless=True,
    width=1280,
    height=1440,
    # height=720, # NOTE
    locale="en-US",
    args=(),
    video_dir=None,
    navigation_timeout=16000,
    timeout=5000,
):
    browser = await playwright.chromium.launch(
        traces_dir=None,
        headless=headless,
        args=[
            "--incognito",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
            "--disable-features=CrossSiteDocumentBlockingAlways,CrossSiteDocumentBlockingIfIsolating",
            *args,
        ],
        chromium_sandbox=True if not os.getenv("DOCKER") else False,
        ignore_default_args=["--hide-scrollbars"],
    )
    context = await browser.new_context(
        storage_state=storage_state,
        user_agent=USER_AGENT,
        viewport={"width": width, "height": height},
        locale=locale,
        record_video_dir=video_dir,
        # record_har_path=har_path,
        # geolocation=geolocation,
    )
    context.set_default_timeout(timeout)
    context.set_default_navigation_timeout(navigation_timeout)
    # BUG in Playwright:
    page = await context.new_page()
    await page.goto(start_url)  # state_url
    content = await page.content()
    await aprint("went to", start_url)
    return Browser(browser, context, page, screen_size=(height, width))


async def make_browsers(
    playwright: Playwright,
    start_urls: list[str],
    storage_states: list[str | None],
    headless=True,
    width=1280,
    height=1440,
    # height=720, # NOTE
    locale="en-US",
    args=(),
    video_dirs=None,
    navigation_timeout=16000,
    timeout=5000,
):
    browser = await playwright.chromium.launch(
        traces_dir=None,
        headless=headless,
        args=[
            "--incognito",
            "--disable-blink-features=AutomationControlled",
            "--ignore-certificate-errors",
            "--disable-features=CrossSiteDocumentBlockingAlways,CrossSiteDocumentBlockingIfIsolating",
            *args,
        ],
        chromium_sandbox=True if not os.getenv("DOCKER") else False,
        ignore_default_args=["--hide-scrollbars"],
    )

    async def __make(storage_state, start_url, video_dir):
        context = await browser.new_context(
            storage_state=storage_state,
            user_agent=USER_AGENT,
            viewport={"width": width, "height": height},
            locale=locale,
            record_video_dir=video_dir,
        )
        context.set_default_timeout(timeout)
        context.set_default_navigation_timeout(navigation_timeout)
        page = await context.new_page()
        await aprint("made new_page")
        await page.goto(start_url)
        await aprint("went to", start_url)
        return Browser(browser, context, page, screen_size=(height, width))

    return await asyncio.gather(
        *[
            __make(storage_state, start_url, video_dir)
            for storage_state, start_url, video_dir in zip(
                storage_states, start_urls, video_dirs or [None] * len(storage_states)
            )
        ]
    )
