"""验证 Temu / TikTok 登录是否成功"""
import asyncio
import os
import sys
from pathlib import Path

os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]

    # 测试 1: Temu search 是否不再被跳 login
    p = await ctx.new_page()
    print("--- Temu 搜索测试 ---")
    await p.goto("https://www.temu.com/search_result.html?search_key=smart+guitar", timeout=30000)
    await asyncio.sleep(4)
    print(f"URL: {p.url}")
    print(f"Title: {await p.title()}")
    goods_links = await p.evaluate("() => document.querySelectorAll('a[href*=\"goods\"]').length")
    print(f"goods 链接数: {goods_links}")
    if "login" in p.url.lower():
        print("❌ Temu 还在要求登录")
    elif goods_links > 0:
        print("✅ Temu 登录生效，能看到商品")
    else:
        print("⚠️  Temu 页面加载了但没找到商品卡")
    await p.close()

    # 测试 2: TikTok Shop
    p2 = await ctx.new_page()
    print("\n--- TikTok Shop 搜索测试 ---")
    await p2.goto("https://www.tiktok.com/shop/s/smart%20guitar", timeout=30000)
    await asyncio.sleep(5)
    print(f"URL: {p2.url}")
    print(f"Title: {await p2.title()}")
    product_links = await p2.evaluate("() => document.querySelectorAll('a[href*=\"/pdp/\"], a[href*=\"/product/\"]').length")
    print(f"商品链接数: {product_links}")
    if any(k in p2.url.lower() for k in ("login", "captcha", "verify")):
        print(f"❌ TikTok Shop 还在要求登录/验证")
    elif product_links > 0:
        print("✅ TikTok Shop 登录生效，能看到商品")
    else:
        print("⚠️  页面加载了但没找到商品卡")
    await p2.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
