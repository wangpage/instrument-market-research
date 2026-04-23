import asyncio
import os
import sys
from pathlib import Path

os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.temu import TemuScraper


async def main():
    async with TemuScraper() as s:
        page = await s._context.new_page()
        url = "https://www.temu.com/search_result.html?search_key=smart+guitar"
        print(f"Navigating: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        print(f"page.url = {page.url}")
        print(f"page.title = {await page.title()}")
        await page.screenshot(path="/tmp/temu_test.png")
        html = await page.content()
        Path("/tmp/temu_test.html").write_text(html, encoding="utf-8")
        print(f"HTML size: {len(html)}")
        # 找商品链接
        for sel in ['a[href*="/goods"]', 'a[href*="goods_id"]', '[data-testid*="product"]', '.searchResultList img']:
            count = await page.evaluate(f"() => document.querySelectorAll('{sel}').length")
            print(f"  {sel}: {count}")
        await page.close()


if __name__ == "__main__":
    asyncio.run(main())
