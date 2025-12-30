import re
import asyncio  # 替换 time
import logging
from urllib.parse import unquote
# 注意：在 Async 环境下，不需要导入 sync_playwright，仅需导入类型提示
from playwright.async_api import Route, Request

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# 弹窗 JS (保持不变)
OVERLAY_JS = """
<script>
document.addEventListener("DOMContentLoaded", function popupHandler() {
    // Check localStorage to see if the pop-up has been closed
    if (!localStorage.getItem("popupClosed")) {
        // Create overlay
        var overlay = document.createElement("div");
        overlay.id = "my-overlay";
        overlay.style.position = "fixed";
        overlay.style.top = "0";
        overlay.style.left = "0";
        overlay.style.width = "100%";
        overlay.style.height = "100%";
        overlay.style.backgroundColor = "rgba(0, 0, 0, 0.8)";
        overlay.style.display = "flex";
        overlay.style.zIndex = "9999";
        overlay.style.pointerEvents = "auto";

        // Disable all interactions on the rest of the page
        document.body.style.pointerEvents = "none";  // Disable all pointer events on the body
        document.body.style.overflow = "hidden";  // Disable scrolling

        // Create popup
        var popup = document.createElement("div");
        popup.style.position = "relative";
        popup.style.backgroundColor = "white";
        popup.style.padding = "20px";
        popup.style.borderRadius = "10px";
        popup.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.1)";
        popup.style.top = "700px"; // distance from the top
        popup.style.left = "600px"; // distance from the left
        popup.style.width = "400px"; // width of popup
        popup.style.height = "100px"; // height of popup

        popup.innerHTML = `
            <span id="close-popup" style="
                position: absolute;
                top: -20px;  /* Moves the close button higher */
                right: 5px;
                font-size: 24px;
                font-weight: bold;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: red;
                color: white;
                border-radius: 50%;
                cursor: pointer;
                user-select: none;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
            ">✖</span>

            <p style="margin-top: 30px;">This is a test popup!</p>
        `;

        // Append popup to overlay
        overlay.appendChild(popup);
        document.body.appendChild(overlay);

        // Close the popup when the X is clicked
        document.getElementById("close-popup").addEventListener("click", function() {
            document.body.removeChild(overlay);
            localStorage.setItem("popupClosed", "true"); // Store flag in localStorage
            document.body.style.pointerEvents = "auto";  // Re-enable pointer events after popup is closed
            document.body.style.overflow = "auto";  // Re-enable scrolling

            // Send a signal to the server to stop interception
            fetch("/popup-closed", { method: "POST" });

            // remove event listener when we remove pop-up so if we want to intercept again it can
            document.removeEventListener("DOMContentLoaded", popupHandler);
            localStorage.removeItem("popupClosed");
        });
    }
});
</script>

"""

class InterferenceController:
    def __init__(self, addon_mode=1, target_keys=None):
        self.addon = addon_mode
        self.target_keys = target_keys if target_keys else [
            '172.26.116.102:8080', 'localhost:8000', '172.26.116.102:8081', 'dockerized-magento.local', 'localhost:7780'
        ]
        self.active_env = None 
        self.start_patterns = {
            key: re.compile(rf'http://{key}.*\?logging=Starting(.*)') for key in self.target_keys
        }
        self.end_patterns = {
            key: re.compile(rf'http://{key}.*\?logging=Ending(.*)') for key in self.target_keys
        }

    def log(self, msg):
        print(f"[Controller] {msg}")

    # 注意：这里改为了 async def
    async def route_handler(self, route: Route):
        request = route.request
        url = request.url
        
        # --- 1. 状态检查与切换逻辑 ---
        for key in self.target_keys:
            start_match = self.start_patterns[key].search(url)
            if start_match:
                decoded = unquote(start_match.group(1))
                self.log(f"🟢 Task START detected for {key}. Msg: {decoded}")
                self.active_env = key 
                await route.continue_() # await
                return

            end_match = self.end_patterns[key].search(url)
            if end_match:
                decoded = unquote(end_match.group(1))
                self.log(f"🔴 Task END detected for {key}. Msg: {decoded}")
                self.active_env = None 
                await route.continue_() # await
                return

        # --- 2. 监听弹窗关闭信号 ---
        if "/popup-closed" in url and request.method == "POST":
            self.log("✅ Popup closed signal received.")
            await route.fulfill(status=200, body="OK") # await
            return

        # --- 3. 干扰注入逻辑 ---
        if self.active_env:
            if self.active_env not in url:
                await route.continue_()
                return

            # === Addon 2: 500 Error ===
            if self.addon == 2:
                self.log(">>> Injecting 500 Error")
                await route.fulfill(
                    status=500,
                    content_type="text/html",
                    body="<html><body><h1>500 Server Error (Injected)</h1></body></html>"
                )
                return

            # === Addon 3: Network Delay ===
            if self.addon == 3:
                self.log(">>> Injecting 10s Delay")
                # 关键修改：使用 asyncio.sleep 而不是 time.sleep，避免阻塞
                await asyncio.sleep(10) 
                await route.continue_() 
                return

            # === Addon 1: Popup (修改响应体) ===
            if self.addon == 1:
                try:
                    # 关键修改：await route.fetch()
                    response = await route.fetch()
                    content_type = response.headers.get("content-type", "")
                    
                    if "text/html" in content_type:
                        # 这是一个异步方法，需要 await text()
                        body = await response.text()
                        if "</html>" in body:
                            self.log(f">>> Injecting Popup JS into HTML: {url}")
                            new_body = body.replace("</html>", OVERLAY_JS + "</html>")
                            await route.fulfill(response=response, body=new_body)
                            return
                    
                    # 关键修复：如果不是 HTML (如 CSS/JS/Images)，
                    # 必须把刚才 fetch 到的原样还回去！
                    # 不能用 route.continue_()，因为 fetch() 已经接管了请求。
                    await route.fulfill(response=response)
                    return

                except Exception as e:
                    self.log(f"Error fetching original response: {e}")
                    # 出错了尝试放行
                    try:
                        await route.continue_()
                    except:
                        pass
                    return

        # 默认放行
        await route.continue_()