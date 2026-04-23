"""
Playwright 基类，所有反爬强的平台都走这里。

三种模式（环境变量 BROWSER_MODE 切换）：
- headed (默认): 弹出真实 Chromium 窗口，能通过绝大多数反爬
- cdp: 连接你已开的 Chrome/Chromium（需 Chrome 用 --remote-debugging-port=9222 启动）
  → 带你真实的 cookie、history、插件，反反爬最强
- headless: 无头（最容易被检测，仅用于调试 / CI）

模拟人类行为：
- 随机滚动 / 停顿
- 小范围鼠标移动
- 请求间 2-8s 真实间隔
"""
import asyncio
import json
import logging
import os
import random
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
BROWSER_STATE_DIR = ROOT / "browser_state"
BROWSER_STATE_DIR.mkdir(parents=True, exist_ok=True)

UA_DESKTOP = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class BrowserBaseScraper:
    """子类设置 platform (用作 storage_state 文件名 + raw 目录)"""
    platform: str = ""

    def __init__(self, proxy=None, mode=None):
        self.proxy = proxy or os.getenv("HTTPS_PROXY")
        self.mode = (mode or os.getenv("BROWSER_MODE") or "headed").lower()
        self._pw = None
        self._browser = None
        self._context = None
        self._state_file = BROWSER_STATE_DIR / f"{self.platform}.json"

    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()

        if self.mode == "cdp":
            cdp_url = os.getenv("CDP_URL", "http://localhost:9222")
            log.info(f"[{self.platform}] connecting to existing Chrome via CDP: {cdp_url}")
            self._browser = await self._pw.chromium.connect_over_cdp(cdp_url)
            ctxs = self._browser.contexts
            if ctxs:
                self._context = ctxs[0]
            else:
                self._context = await self._browser.new_context()
        else:
            headless = self.mode == "headless"
            launch_kwargs = {
                "headless": headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            }
            if self.proxy:
                launch_kwargs["proxy"] = {"server": self.proxy}
            self._browser = await self._pw.chromium.launch(**launch_kwargs)

            ctx_kwargs = dict(
                user_agent=UA_DESKTOP,
                viewport={"width": random.randint(1366, 1680), "height": random.randint(800, 1050)},
                locale="en-US",
                timezone_id="America/New_York",
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                },
            )
            if self._state_file.exists():
                ctx_kwargs["storage_state"] = str(self._state_file)
            self._context = await self._browser.new_context(**ctx_kwargs)

        # 注入反检测脚本（基础 stealth）
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = {runtime: {}};
        """)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._context and self.mode != "cdp":
            try:
                await self._context.storage_state(path=str(self._state_file))
            except Exception:
                pass
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser and self.mode != "cdp":
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw:
            await self._pw.stop()

    # —— 人类行为模拟 ——
    async def _human_pause(self, lo=1.5, hi=4.0):
        await asyncio.sleep(random.uniform(lo, hi))

    async def _human_scroll(self, page, steps=None):
        steps = steps or random.randint(3, 6)
        for _ in range(steps):
            delta = random.randint(300, 900)
            await page.mouse.wheel(0, delta)
            await self._human_pause(0.4, 1.2)

    async def _human_mousemove(self, page):
        try:
            viewport = page.viewport_size
            if not viewport:
                return
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, viewport["width"] - 100)
                y = random.randint(100, viewport["height"] - 100)
                await page.mouse.move(x, y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass

    async def _goto_like_human(self, page, url, wait_until="domcontentloaded"):
        await page.goto(url, wait_until=wait_until, timeout=60000)
        await self._human_pause(2.0, 4.0)
        await self._human_mousemove(page)
        await self._human_scroll(page, steps=random.randint(2, 4))

    async def _is_blocked(self, page):
        url = page.url.lower()
        if any(k in url for k in ("captcha", "splashui", "challenge", "guard", "robot")):
            return True
        title = (await page.title()).lower()
        if any(k in title for k in ("captcha", "robot check", "verify", "challenge")):
            return True
        return False

    # —— 数据持久化 ——
    def _save_raw(self, kind, query, payload):
        outdir = ROOT / "data" / "raw" / self.platform
        outdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe = str(query).replace(" ", "_").replace("/", "-")[:80]
        fp = outdir / f"{kind}_{safe}_{ts}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
