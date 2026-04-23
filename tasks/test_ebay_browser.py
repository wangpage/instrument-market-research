import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("BROWSER_MODE", "headed")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from scrapers.ebay import EbayScraper


async def main():
    async with EbayScraper() as s:
        ps = await s.search("smart", "smart_guitar", "smart guitar", True, 10)
        print(f"\n=== got {len(ps)} products ===")
        for p in ps[:8]:
            print(f"  ${p.price_usd}  | {p.title[:80]}  | id={p.asin_or_sku} | loc={p.seller_country}")


if __name__ == "__main__":
    asyncio.run(main())
