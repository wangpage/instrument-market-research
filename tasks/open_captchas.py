"""在 CDP Chrome 里打开 Temu / TikTok Shop search 页，让用户手动通过 CAPTCHA"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]

    # 醒目红色提示
    p0 = await ctx.new_page()
    await p0.goto("data:text/html,<html><body style='background:#ff3b30;color:white;font-family:-apple-system;text-align:center;padding:80px;'><h1 style='font-size:50px;'>👇 请手动完成 Temu 和 TikTok Shop 的 CAPTCHA 验证 👇</h1><p style='font-size:24px;'>切换到下面 2 个 tab，分别完成验证。完成后回对话告诉我'OK'</p></body></html>")

    # Temu search → 触发几何验证
    p1 = await ctx.new_page()
    await p1.goto("https://www.temu.com/search_result.html?search_key=guitar", timeout=30000)
    print("✅ Temu search 页打开")

    # TikTok Shop search → 触发滑动验证
    p2 = await ctx.new_page()
    await p2.goto("https://www.tiktok.com/shop/", timeout=30000)
    print("✅ TikTok Shop 页打开")

    # 把红色提示置顶
    await p0.bring_to_front()
    print("\n请切到 CDP Chrome 窗口（红色提示页），完成 Temu + TikTok 的 CAPTCHA")
    print("完成后回话告诉我 'OK'，我立即跑全量")

    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
