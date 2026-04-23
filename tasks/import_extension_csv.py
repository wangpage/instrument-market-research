"""导入 Chrome 扩展导出的 CSV/JSON。
- 读 data/incoming/*.csv 或 *.json
- 按 platform 拆分
- 过 analysis/normalize 的过滤器（is_accessory + 白名单 + 价格下限 + 货币转换）
- 输出到 data/processed/products_<platform>.xlsx（合并已有数据，按 asin_or_sku 去重）
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.schema import Product
from config.keywords import CATEGORIES
from analysis.normalize import products_to_df
from analysis.report import write_products_master


# query_keyword (lower) -> (category, subcategory, is_smart)
QUERY_MAP: dict[str, tuple[str, str, bool]] = {}
for _spec in CATEGORIES:
    for _q in _spec.queries:
        QUERY_MAP[_q.lower().strip()] = (_spec.category, _spec.subcategory, _spec.is_smart)


def resolve_from_query(query: str):
    if not query:
        return None
    q = str(query).lower().strip()
    if q in QUERY_MAP:
        return QUERY_MAP[q]
    # 退而求其次：子串包含
    for k, v in QUERY_MAP.items():
        if k in q or q in k:
            return v
    return None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("import_ext")

INCOMING = ROOT / "data/incoming"
PROCESSED = ROOT / "data/processed"


def load_csv(fp: Path) -> list[dict]:
    df = pd.read_csv(fp)
    # 把 NaN 替换成 None
    df = df.astype(object).where(pd.notna(df), None)
    if "is_smart_instrument" in df.columns:
        df["is_smart_instrument"] = df["is_smart_instrument"].map(
            lambda v: (str(v).lower() in ("true", "1", "yes")) if v is not None else False
        )
    return df.to_dict(orient="records")


def load_json(fp: Path) -> list[dict]:
    return json.loads(fp.read_text(encoding="utf-8"))


def _clean_val(v):
    import math
    if v is None or v == "":
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    return v


def to_products(rows: list[dict]) -> list[Product]:
    out = []
    skipped = {"empty": 0, "validation": 0}
    first_err = None
    for r in rows:
        clean = {k: _clean_val(v) for k, v in r.items()}
        if not clean.get("platform") or not clean.get("title") or not clean.get("asin_or_sku"):
            skipped["empty"] += 1
            continue
        clean.setdefault("query_keyword", "")
        # 若 subcategory 缺失/unknown，从 query_keyword 反查
        if not clean.get("subcategory") or clean.get("subcategory") == "unknown":
            resolved = resolve_from_query(clean.get("query_keyword"))
            if resolved:
                clean["category"], clean["subcategory"], smart = resolved
                if not clean.get("is_smart_instrument"):
                    clean["is_smart_instrument"] = smart
        clean["category"] = clean.get("category") or "unknown"
        clean["subcategory"] = clean.get("subcategory") or "unknown"
        clean["rank_in_search"] = clean.get("rank_in_search") or 0
        clean["url"] = clean.get("url") or f"#missing-{clean['asin_or_sku']}"
        try:
            out.append(Product(**clean))
        except Exception as e:
            skipped["validation"] += 1
            if first_err is None:
                first_err = str(e)[:500]
    log.info(f"skipped: {skipped}  first_validation_err: {first_err}")
    return out


def merge_with_existing(new_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = PROCESSED / f"products_{platform}.xlsx"
    if not out.exists():
        return new_df
    try:
        old = pd.read_excel(out, sheet_name="all_products")
    except Exception:
        return new_df
    combined = pd.concat([old, new_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["platform", "asin_or_sku"], keep="last")
    return combined


def main():
    files = sorted(list(INCOMING.glob("*.csv")) + list(INCOMING.glob("*.json")))
    if not files:
        log.warning(f"nothing to import in {INCOMING}/ (put CSV/JSON there)")
        return

    all_rows = []
    for fp in files:
        log.info(f"reading {fp.name}")
        rows = load_csv(fp) if fp.suffix.lower() == ".csv" else load_json(fp)
        log.info(f"  {len(rows)} raw rows")
        all_rows.extend(rows)

    products = to_products(all_rows)
    log.info(f"parsed {len(products)} valid Product objects (of {len(all_rows)} raw rows)")

    # 按 platform 拆分
    by_platform: dict[str, list[Product]] = {}
    for p in products:
        by_platform.setdefault(p.platform, []).append(p)

    for platform, items in by_platform.items():
        log.info(f"[{platform}] {len(items)} raw -> normalizing")
        df = products_to_df(items)
        if df.empty:
            log.warning(f"[{platform}] nothing left after filter")
            continue
        merged = merge_with_existing(df, platform)
        # Excel 不支持 tz-aware datetime
        for col in merged.columns:
            if pd.api.types.is_datetime64_any_dtype(merged[col]):
                try:
                    merged[col] = merged[col].dt.tz_localize(None)
                except (TypeError, AttributeError):
                    merged[col] = merged[col].dt.tz_convert(None)
            elif merged[col].dtype == object:
                merged[col] = merged[col].apply(
                    lambda v: v.replace(tzinfo=None) if hasattr(v, "tzinfo") and getattr(v, "tzinfo", None) else v
                )
        out = PROCESSED / f"products_{platform}.xlsx"
        write_products_master(merged, out)
        log.info(f"[{platform}] wrote {len(merged)} rows (new {len(df)}, merged with existing) -> {out.name}")

    # 归档 incoming 文件
    archive = INCOMING / "archived"
    archive.mkdir(exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    for fp in files:
        new_name = archive / f"{fp.stem}_{ts}{fp.suffix}"
        fp.rename(new_name)
        log.info(f"archived {fp.name} -> archived/{new_name.name}")


if __name__ == "__main__":
    main()
