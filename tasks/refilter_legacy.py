"""把旧备份里的 walmart / temu 记录过一遍新的 normalize 过滤器，
输出 products_walmart.xlsx / products_temu.xlsx 供 build_report 合并"""
import logging
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.normalize import is_accessory, title_matches_subcategory
from config.keywords import min_price_for
from analysis.report import write_products_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("refilter")


def refilter(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=["platform", "asin_or_sku"], keep="first")
    after_dedup = len(df)

    mask_acc = df["title"].fillna("").apply(is_accessory)
    df = df[~mask_acc]
    after_acc = len(df)

    mask_wl = df.apply(
        lambda r: title_matches_subcategory(r.get("title", ""), r.get("subcategory", "")),
        axis=1,
    )
    df = df[mask_wl]
    after_wl = len(df)

    df = df.copy()
    df["_min"] = df["subcategory"].apply(min_price_for)
    price_ok = df["price_usd"].isna() | (df["price_usd"] >= df["_min"])
    df = df[price_ok].drop(columns=["_min"])
    after_price = len(df)

    log.info(
        f"{before} -> dedup {after_dedup} -> accessory {after_acc} "
        f"-> whitelist {after_wl} -> min_price {after_price}"
    )
    return df


def main():
    processed = ROOT / "data/processed"
    backups = sorted(processed.glob("products_master.bak_*.xlsx"))
    if not backups:
        log.error("no backup found")
        return
    src = backups[-1]
    log.info(f"reading from {src.name}")
    df = pd.read_excel(src, sheet_name="all_products")

    for platform in ["walmart", "temu"]:
        part = df[df["platform"] == platform].copy()
        if part.empty:
            log.warning(f"{platform}: no rows in backup")
            continue
        log.info(f"[{platform}] starting with {len(part)} rows")
        kept = refilter(part)
        out = processed / f"products_{platform}.xlsx"
        write_products_master(kept, out)
        log.info(f"[{platform}] wrote {len(kept)} -> {out.name}")


if __name__ == "__main__":
    main()
