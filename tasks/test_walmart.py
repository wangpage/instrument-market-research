import asyncio
import os
import sys
from pathlib import Path

os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.walmart import WalmartScraper


async def main():
    async with WalmartScraper() as s:
        page = await s._context.new_page()
        url = "https://www.walmart.com/search?q=smart+guitar"
        print(f"Navigating: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        print(f"page.url = {page.url}")
        print(f"page.title = {await page.title()}")
        await page.screenshot(path="/tmp/walmart_test.png", full_page=False)
        html = await page.content()
        Path("/tmp/walmart_test.html").write_text(html, encoding="utf-8")
        print(f"HTML size: {len(html)}")
        # Check NEXT_DATA
        nd = await page.evaluate("() => { const el = document.getElementById('__NEXT_DATA__'); return el ? el.textContent.length : 0; }")
        print(f"__NEXT_DATA__ size: {nd}")
        # Try common product card selectors
        for sel in ['div[data-item-id]', 'a[link-identifier]', '[data-testid="search-results"]', 'section[data-testid="results-section"]']:
            count = await page.evaluate(f"() => document.querySelectorAll('{sel}').length")
            print(f"  {sel}: {count}")
        await page.close()


if __name__ == "__main__":
    asyncio.run(main())
