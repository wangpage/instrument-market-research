"""查明 CDP Chrome 里当前所有 tab URL 和 cookie 状态"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctxs = browser.contexts
    print(f"Contexts: {len(ctxs)}")
    all_pages = []
    for ctx in ctxs:
        all_pages.extend(ctx.pages)
    print(f"Total open pages: {len(all_pages)}")
    for p in all_pages:
        try:
            url = p.url
            title = await p.title()
            print(f"  • [{title[:40]}]  {url[:100]}")
        except Exception as e:
            print(f"  • error: {e}")

    # 检查 cookies
    for ctx in ctxs:
        print("\n--- Temu cookies ---")
        temu_cookies = await ctx.cookies("https://www.temu.com")
        critical = [c for c in temu_cookies if c["name"] in ("PassKey", "dilx", "api_uid", "user_uin", "userId", "login")]
        print(f"  total: {len(temu_cookies)}, critical: {len(critical)}")
        for c in critical:
            v = c.get("value", "")
            print(f"    {c['name']}={v[:40]}...")

        print("\n--- TikTok cookies ---")
        tt_cookies = await ctx.cookies("https://www.tiktok.com")
        critical = [c for c in tt_cookies if c["name"] in ("sessionid", "sid_tt", "sid_guard", "uid_tt", "tt_csrf_token", "tt-target-idc")]
        print(f"  total: {len(tt_cookies)}, critical: {len(critical)}")
        for c in critical:
            v = c.get("value", "")
            print(f"    {c['name']}={v[:40]}...")
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
