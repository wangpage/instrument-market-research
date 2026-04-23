"""给已有 products Excel 里按 review_count 排前的 SKU 抓评论"""
import asyncio
import logging
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers.amazon import AmazonScraper
from analysis.normalize import reviews_to_df
from analysis.report import write_reviews_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_top_reviews")


async def main(top_k=30, reviews_per_sku=15):
    df = pd.read_excel(ROOT / "data/processed/products_amazon.xlsx", sheet_name="all_products")
    df = df[df["platform"] == "amazon"]
    df = df.dropna(subset=["review_count"])
    df = df.sort_values("review_count", ascending=False).head(top_k)
    log.info(f"fetching reviews for top {len(df)} SKUs (by review_count)")

    all_reviews = []
    async with AmazonScraper() as s:
        for _, row in df.iterrows():
            sku = row["asin_or_sku"]
            try:
                revs = await s.fetch_reviews(sku, reviews_per_sku)
                all_reviews.extend(revs)
                log.info(f"  {sku}: got {len(revs)} reviews (title={row['title'][:60]!r})")
            except Exception as e:
                log.warning(f"  {sku}: failed: {e}")

    df_r = reviews_to_df(all_reviews)
    out = ROOT / "data/processed/reviews_amazon.xlsx"
    if not df_r.empty:
        write_reviews_master(df_r, out)
        log.info(f"wrote {len(df_r)} reviews → {out}")
    else:
        log.warning("no reviews captured")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--top-k", type=int, default=30)
    p.add_argument("--per-sku", type=int, default=15)
    args = p.parse_args()
    asyncio.run(main(args.top_k, args.per_sku))
