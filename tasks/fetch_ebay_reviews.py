"""抓 eBay Top 30 SKU 的 item-level 评论 (或评分最高的买家反馈)"""
import asyncio
import os
import sys
import re
from pathlib import Path
import pandas as pd

os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from scrapers.browser_base import BrowserBaseScraper
from config.schema import Review
from analysis.normalize import reviews_to_df
from analysis.report import write_reviews_master
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent


class EbayReviewFetcher(BrowserBaseScraper):
    platform = "ebay"

    async def get_reviews(self, sku, top_n=10):
        """eBay 商品详情页抓 'Reviews' 部分"""
        page = await self._context.new_page()
        reviews = []
        url = f"https://www.ebay.com/itm/{sku}"
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                return []
            # 滚到评论区
            await self._human_scroll(page, steps=6)
            await self._human_pause(1.0, 2.0)
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            # eBay 评论的多种可能结构
            blocks = soup.select(
                "[data-testid*='review'], .rvw-section article, "
                ".ux-product-reviews__review, .ux-layout-section-module__row--review, "
                "#Reviews article, [class*='review-item']"
            )
            for idx, b in enumerate(blocks[:top_n]):
                text = b.get_text(" ", strip=True)
                if not text or len(text) < 20:
                    continue
                rating = None
                rm = re.search(r"(\d(?:\.\d)?)\s*out of", text)
                if rm:
                    try:
                        rating = float(rm.group(1))
                    except ValueError:
                        pass
                reviews.append(Review(
                    platform="ebay",
                    asin_or_sku=sku,
                    review_id=f"{sku}_{idx}",
                    rating=rating,
                    body=text[:1500],
                ))
        except Exception as e:
            log.warning(f"[ebay] review error {sku}: {e}")
        finally:
            await page.close()
        self._save_raw("reviews", sku, [r.model_dump() for r in reviews])
        return reviews


log = logging.getLogger("ebay_reviews")


async def main(top_k=30, per_sku=10):
    df = pd.read_excel(ROOT / "data/processed/products_ebay.xlsx", sheet_name="all_products")
    # eBay 没有 review_count 可用排序，用 rank_in_search（前排热门）
    df = df.sort_values(["rank_in_search"]).drop_duplicates("asin_or_sku").head(top_k)
    log.info(f"fetching reviews for {len(df)} eBay SKUs")

    all_reviews = []
    async with EbayReviewFetcher() as s:
        for _, row in df.iterrows():
            sku = row["asin_or_sku"]
            try:
                revs = await s.get_reviews(sku, per_sku)
                all_reviews.extend(revs)
                log.info(f"  {sku}: {len(revs)} reviews ({row['title'][:50]})")
            except Exception as e:
                log.warning(f"  {sku}: fail: {e}")

    df_r = reviews_to_df(all_reviews)
    if not df_r.empty:
        out = ROOT / "data/processed/reviews_ebay.xlsx"
        write_reviews_master(df_r, out)
        log.info(f"wrote {len(df_r)} reviews → {out}")
    else:
        log.warning("no reviews captured")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--top-k", type=int, default=30)
    p.add_argument("--per-sku", type=int, default=10)
    args = p.parse_args()
    asyncio.run(main(args.top_k, args.per_sku))
