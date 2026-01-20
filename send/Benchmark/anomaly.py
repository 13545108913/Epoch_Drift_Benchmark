import re
import time
import random
import logging
from urllib.parse import unquote
from playwright.sync_api import sync_playwright, Route, Request

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

        });
    }
});
</script>

"""

class InterferenceController:
    def __init__(self, addon_mode=1, target_keys=None):
        self.addon = addon_mode
        # 定义需要监听的目标环境 Key (域名:端口 或 域名)
        self.target_keys = target_keys if target_keys else [
            '172.26.116.102:8080', 'localhost:8000', '172.26.116.102:8081', 'dockerized-magento.local', 'localhost:7780'
        ]
        
        # 状态管理：当前激活的环境
        self.active_env = None 

        self.popup_closed_state = False
        
        # 预编译正则，用于检测开始和结束
        # 逻辑：http://{key}.*?logging=Starting(.*)
        self.start_patterns = {
            key: re.compile(rf'http://{key}.*\?logging=Starting(.*)') for key in self.target_keys
        }
        self.end_patterns = {
            key: re.compile(rf'http://{key}.*\?logging=Ending(.*)') for key in self.target_keys
        }

    def log(self, msg):
        print(f"[Controller] {msg}")

    def route_handler(self, route: Route):
        request = route.request
        url = request.url
        
        # --- 1. 状态检查与切换逻辑 ---
        
        # 遍历所有 Key，检查是否触发了 开始 或 结束
        for key in self.target_keys:
            # 检查开始
            start_match = self.start_patterns[key].search(url)
            if start_match:
                decoded = unquote(start_match.group(1))
                self.log(f"🟢 Task START detected for {key}. Msg: {decoded}")
                self.active_env = key # 激活当前环境
                self.popup_closed_state = False
                # 继续请求，不拦截这个控制信号本身
                route.continue_()
                return

            # 检查结束
            end_match = self.end_patterns[key].search(url)
            if end_match:
                decoded = unquote(end_match.group(1))
                self.log(f"🔴 Task END detected for {key}. Msg: {decoded}")
                self.active_env = None # 关闭干扰
                self.popup_closed_state = False
                route.continue_()
                return

        # --- 2. 监听弹窗关闭信号 ---
        if "/popup-closed" in url and request.method == "POST":
            self.log("✅ Popup closed signal received.")
            # 这里可以根据需要添加逻辑，例如 "允许通过" 或 "关闭拦截"
            self.popup_closed_state = True
            # 返回 200 OK 也要加上 CORS 头，防止 JS 报错
            route.fulfill(
                status=200, 
                body="OK",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Private-Network": "true"
                }
            )
            return

        # --- 3. 干扰注入逻辑 (仅当 active_env 有值时执行) ---
        
        if self.active_env:
            # 简单判断：只有当请求的 URL 包含当前激活的 Key 时才拦截 (防止误伤第三方资源)
            if self.active_env not in url:
                route.continue_()
                return
            
            # 如果弹窗模式已开启，但之前已经收到过关闭信号，则不再注入
            if self.addon == 1 and self.popup_closed_state:
                # self.log("🚫 Popup already closed, skipping injection.")
                route.continue_()
                return

            self.log(f"⚡ Intercepting request in active env: {url}")

            # === Addon 2: 500 Error ===
            if self.addon == 2:
                self.log(">>> Injecting 500 Error")
                route.fulfill(
                    status=500,
                    content_type="text/html",
                    body="<html><body><h1>500 Server Error (Injected)</h1></body></html>"
                )
                return

            # === Addon 3: Network Delay ===
            if self.addon == 3:
                self.log(">>> Injecting 10s Delay")
                time.sleep(10)
                # 延迟后可以选择 abort (断网) 或者 continue (慢网)
                route.continue_() 
                return

            # === Addon 1: Popup (修改响应体) ===
            if self.addon == 1:
                # 获取原始响应
                try:
                    response = route.fetch()
                    content_type = response.headers.get("content-type", "")
                    
                    # 只拦截 HTML
                    if "text/html" in content_type:
                        body = response.text()
                        # 注入 JS 到 </html> 之前
                        if "</html>" in body:
                            self.log(">>> Injecting Popup JS into HTML")
                            new_body = body.replace("</html>", OVERLAY_JS + "</html>")
                            route.fulfill(response=response, body=new_body)
                            return
                except Exception as e:
                    self.log(f"Error fetching original response: {e}")
                    route.continue_()
                    return

        # 如果没有激活，或者不符合干扰条件，直接放行
        route.continue_()