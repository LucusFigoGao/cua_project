import os
import asyncio
from playwright.async_api import async_playwright
from e2b import Sandbox
from IPython.display import IFrame

E2B_DOMAIN = os.environ.get("E2B_DOMAIN")
E2B_API_KEY = os.environ.get("E2B_API_KEY")

# 创建浏览器沙箱，运行时间设置为 1 小时，template 需要替换为上述控制台新建的工具名称
sandbox = Sandbox.create(template="browser-2qjk8ulodpe", timeout=3600)
print(f"browser sandbox created: {sandbox.sandbox_id}")

novnc_url = f"https://{sandbox.get_host(9000)}/novnc/vnc_lite.html?&path=websockify?access_token={sandbox._envd_access_token}"
# 打印 vnc url，您可以复制该 url 并在浏览器中打开，查看浏览器界面
print(f"vnc url: {novnc_url}")

# 通过 CDP 协议连接到远程浏览器
async def main():
    # 构建 CDP 连接 URL
    cdp_url = f"https://{sandbox.get_host(9000)}/cdp"

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(
            cdp_url, 
            headers={"X-Access-Token": str(sandbox._envd_access_token)}
        )
        context = browser.contexts[0]
        page = context.pages[0]
        
        # 导航到指定界面
        await page.goto("https://tencent.com")
        await page.wait_for_load_state("networkidle")

