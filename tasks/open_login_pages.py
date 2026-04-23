"""在 CDP Chrome 里 bring to front 并打开登录页"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]

    # 1. 清理旧 tab
    for p in list(ctx.pages):
        try:
            if p.url == "about:blank" or "blank" in p.url:
                continue
            await p.close()
        except Exception:
            pass

    # 2. 开一个醒目标识 tab
    marker = await ctx.new_page()
    html = """
    <html><head><title>⬅️ 这里是 CDP Chrome，请在此窗口登录</title></head>
    <body style="background:#ff3b30;color:white;font-family:-apple-system;text-align:center;padding:80px;">
      <h1 style="font-size:60px;">👈 这就是 CDP Chrome</h1>
      <h2>请在这个 Chrome 窗口（独立 profile）里完成登录</h2>
      <p style="font-size:24px;">其他 tab 已经打开 Temu / TikTok 登录页</p>
      <p style="font-size:18px;margin-top:40px;opacity:0.8;">Profile Path: /tmp/chrome-cdp-profile</p>
    </body></html>
    """
    await marker.goto("data:text/html," + html)

    # 3. 登录页（强制英文）
    print("打开 Temu 登录页...")
    p1 = await ctx.new_page()
    await p1.goto("https://www.temu.com/login.html?lang=en", timeout=30000)

    print("打开 TikTok 登录页...")
    p2 = await ctx.new_page()
    await p2.goto("https://www.tiktok.com/login?lang=en", timeout=30000)

    # 4. 强制把 CDP Chrome 窗口置顶（macOS）
    try:
        subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to activate'],
                       check=False, capture_output=True)
    except Exception:
        pass
    # 把标识 tab 激活（前置在最前）
    await marker.bring_to_front()

    print("\n=== 已打开登录页 + 醒目红色标识页 ===")
    print("请切到**最显眼的那个红色提示 Chrome 窗口**，其他 tab 是 Temu/TikTok 登录页")
    print("登录完成后回 'OK'")
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
