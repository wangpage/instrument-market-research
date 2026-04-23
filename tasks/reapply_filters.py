"""加强了货币转换和黑名单后，把所有 products_*.xlsx 重新过一遍 normalize"""
import logging
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.normalize import (
    is_accessory,
    title_matches_subcategory,
    convert_price_to_usd,
)
from config.keywords import min_price_for
from analysis.report import write_products_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("reapply")


def reprocess(df: pd.DataFrame) -> pd.DataFrame:
    """price_usd 已经在 scraper 入库时做过货币转换，这里只重应用标题/价格/白名单过滤。"""
    before = len(df)
    df = df.drop_duplicates(subset=["platform", "asin_or_sku"], keep="first")

    mask_acc = df["title"].fillna("").apply(is_accessory)
    df = df[~mask_acc]

    mask_wl = df.apply(
        lambda r: title_matches_subcategory(r.get("title", ""), r.get("subcategory", "")),
        axis=1,
    )
    df = df[mask_wl]

    df = df.copy()
    df["_min"] = df["subcategory"].apply(min_price_for)
    price_ok = df["price_usd"].isna() | (df["price_usd"] >= df["_min"])
    df = df[price_ok].drop(columns=["_min"])

    log.info(f"{before} -> {len(df)} after reapply")
    return df


def main():
    processed = ROOT / "data/processed"
    for fp in sorted(processed.glob("products_*.xlsx")):
        if fp.stem in ("products_master",):
            continue
        log.info(f"processing {fp.name}")
        df = pd.read_excel(fp, sheet_name="all_products")
        out = reprocess(df)
        write_products_master(out, fp)
        log.info(f"wrote {len(out)} -> {fp.name}")


if __name__ == "__main__":
    main()
