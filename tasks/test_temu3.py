import asyncio, os, sys
from pathlib import Path
os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scrapers.temu import TemuScraper


async def main():
    async with TemuScraper() as s:
        ps = await s.search("smart", "smart_guitar", "smart ukulele", True, 10)
        print(f"got {len(ps)}")
        for p in ps[:6]:
            print(f"  ${p.price_usd}  sold={p.sold_count_text}  {p.title[:70]}  gid={p.asin_or_sku}")


if __name__ == "__main__":
    asyncio.run(main())
