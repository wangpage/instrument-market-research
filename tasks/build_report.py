"""把所有已抓的 products / reviews / summaries 汇总成 master Excel + insights 报告"""
import asyncio
import logging
import sys
import os
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.report import write_products_master, write_reviews_master, write_insights_report, write_summaries
from analysis.pricing import write_charts
from analysis.reviews_ai import summarize_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("build_report")


async def main(with_ai: bool = False, max_ai: int = 30):
    processed = ROOT / "data/processed"

    # 1. 合并所有 products_*.xlsx
    product_dfs = []
    for fp in processed.glob("products_*.xlsx"):
        if fp.stem == "products_master":
            continue
        try:
            df = pd.read_excel(fp, sheet_name="all_products")
            product_dfs.append(df)
            log.info(f"loaded {len(df)} products from {fp.name}")
        except Exception as e:
            log.warning(f"skip {fp}: {e}")

    if not product_dfs:
        log.error("no products files found")
        return

    products_df = pd.concat(product_dfs, ignore_index=True)
    products_df = products_df.drop_duplicates(subset=["platform", "asin_or_sku"], keep="first")
    log.info(f"merged {len(products_df)} unique products")

    # 2. 合并 reviews
    review_dfs = []
    for fp in processed.glob("reviews_*.xlsx"):
        if fp.stem == "reviews_master":
            continue
        try:
            df = pd.read_excel(fp)
            review_dfs.append(df)
            log.info(f"loaded {len(df)} reviews from {fp.name}")
        except Exception as e:
            log.warning(f"skip {fp}: {e}")

    reviews_df = pd.concat(review_dfs, ignore_index=True) if review_dfs else pd.DataFrame()

    # 3. AI 摘要（可选）
    summaries = []
    if with_ai and not reviews_df.empty and os.getenv("ANTHROPIC_API_KEY"):
        log.info(f"running AI summarization on up to {max_ai} SKUs")
        summaries = await summarize_batch(products_df, reviews_df, max_products=max_ai)
    elif with_ai:
        log.warning("skipping AI: need ANTHROPIC_API_KEY and reviews")

    # 4. 写出
    write_products_master(products_df, processed / "products_master.xlsx")
    log.info(f"wrote products_master.xlsx")
    if not reviews_df.empty:
        write_reviews_master(reviews_df, processed / "reviews_master.xlsx")
        log.info(f"wrote reviews_master.xlsx")
    if summaries:
        write_summaries(summaries, processed / "reviews_summaries.xlsx")
        log.info(f"wrote reviews_summaries.xlsx")

    write_charts(products_df, processed / "charts")
    log.info("wrote charts")

    write_insights_report(products_df, summaries, processed / "insights_report.md")
    log.info("wrote insights_report.md")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--with-ai", action="store_true", help="启用 Claude AI 评论摘要（需 ANTHROPIC_API_KEY）")
    p.add_argument("--max-ai", type=int, default=30, help="AI 摘要的最大 SKU 数")
    args = p.parse_args()
    asyncio.run(main(args.with_ai, args.max_ai))
