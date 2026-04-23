import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from config.keywords import CATEGORIES, queries_for_subcategory, all_queries, SUBCATEGORIES
from analysis.normalize import products_to_df, reviews_to_df
from analysis.report import write_products_master, write_reviews_master

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")

DATA_ROOT = Path(__file__).resolve().parent / "data"


SCRAPERS = {}


def register_scrapers():
    from scrapers.amazon import AmazonScraper
    SCRAPERS["amazon"] = AmazonScraper
    try:
        from scrapers.ebay import EbayScraper
        SCRAPERS["ebay"] = EbayScraper
    except ImportError:
        pass
    try:
        from scrapers.walmart import WalmartScraper
        SCRAPERS["walmart"] = WalmartScraper
    except ImportError:
        pass
    try:
        from scrapers.temu import TemuScraper
        SCRAPERS["temu"] = TemuScraper
    except ImportError:
        pass
    try:
        from scrapers.tiktok_shop import TikTokShopScraper
        SCRAPERS["tiktok_shop"] = TikTokShopScraper
    except ImportError:
        pass


async def run_platform(platform: str, category_filter: Optional[str], top_n: int,
                        with_reviews: bool, review_top_n: int):
    Scraper = SCRAPERS[platform]
    all_products = []
    all_reviews = []

    if category_filter:
        tasks_list = queries_for_subcategory(category_filter)
    else:
        tasks_list = all_queries()

    async with Scraper() as s:
        for cat, sub, query, is_smart in tasks_list:
            log.info(f"[{platform}] searching {sub!r} query={query!r}")
            try:
                prods = await s.search(cat, sub, query, is_smart, top_n)
            except Exception as e:
                log.exception(f"[{platform}] search failed: {e}")
                continue
            log.info(f"[{platform}] got {len(prods)} products for {query!r}")
            all_products.extend(prods)

            if with_reviews:
                for p in prods[: min(5, len(prods))]:
                    try:
                        revs = await s.fetch_reviews(p.asin_or_sku, review_top_n)
                        all_reviews.extend(revs)
                        log.info(f"[{platform}] {p.asin_or_sku} reviews={len(revs)}")
                    except Exception as e:
                        log.warning(f"[{platform}] reviews failed for {p.asin_or_sku}: {e}")

    return all_products, all_reviews


async def amain(args):
    register_scrapers()

    if args.platform not in SCRAPERS and args.platform != "all":
        log.error(f"unknown platform: {args.platform}. available: {list(SCRAPERS)}")
        sys.exit(1)

    platforms = list(SCRAPERS) if args.platform == "all" else [args.platform]

    all_products, all_reviews = [], []
    for p in platforms:
        prods, revs = await run_platform(
            p, args.category, args.top_n, args.with_reviews, args.review_top_n
        )
        all_products.extend(prods)
        all_reviews.extend(revs)

    df_p = products_to_df(all_products)
    df_r = reviews_to_df(all_reviews)

    out_products = DATA_ROOT / "processed" / f"products_{args.platform}.xlsx"
    out_reviews = DATA_ROOT / "processed" / f"reviews_{args.platform}.xlsx"

    if not df_p.empty:
        write_products_master(df_p, out_products)
        log.info(f"wrote {len(df_p)} products → {out_products}")
    if not df_r.empty:
        write_reviews_master(df_r, out_reviews)
        log.info(f"wrote {len(df_r)} reviews → {out_reviews}")


def build_parser():
    p = argparse.ArgumentParser(description="跨平台乐器市场调研爬虫")
    p.add_argument("--platform", default="amazon",
                   help="amazon|ebay|walmart|temu|tiktok_shop|all")
    p.add_argument("--category", default=None,
                   help=f"子品类，可选: {SUBCATEGORIES}")
    p.add_argument("--top-n", type=int, default=int(os.getenv("TOP_N_PER_QUERY", "50")),
                   help="每关键词抓 Top N 商品")
    p.add_argument("--review-top-n", type=int, default=int(os.getenv("REVIEW_TOP_N", "20")))
    p.add_argument("--with-reviews", action="store_true", help="同时抓取评论")
    p.add_argument("--all", action="store_true", help="所有平台+所有品类（忽略其他参数）")
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    if args.all:
        args.platform = "all"
        args.category = None
    asyncio.run(amain(args))
