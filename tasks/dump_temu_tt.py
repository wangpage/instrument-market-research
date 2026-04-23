import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]

    for name, url in [
        ("temu", "https://www.temu.com/search_result.html?search_key=smart+guitar"),
        ("tt", "https://www.tiktok.com/shop/s/smart%20guitar"),
    ]:
        p = await ctx.new_page()
        print(f"\n=== {name} ===")
        await p.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(6)
        # 主动滚动触发懒加载
        for _ in range(4):
            await p.mouse.wheel(0, 600)
            await asyncio.sleep(0.8)
        print(f"URL: {p.url}")
        print(f"Title: {await p.title()}")
        html = await p.content()
        Path(f"/tmp/{name}_test.html").write_text(html, encoding="utf-8")
        print(f"HTML size: {len(html)}")
        # 试一些可能的 selectors
        for sel in [
            'a[href*="/goods"]',
            'a[href*="goods_id"]',
            'a[href*="/shop/pdp"]',
            'a[href*="/product/"]',
            '[data-testid*="product"]',
            '[class*="Card"]',
            '[class*="product-card"]',
            '[class*="Product"]',
            'img[alt*="guitar" i]',
        ]:
            n = await p.evaluate(f"() => document.querySelectorAll('{sel}').length")
            print(f"  {sel}: {n}")
        await p.close()

    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
