"""从 data/raw/<platform>/search_*.json 重建 products_<platform>.xlsx，
绕过爬虫网络调用。用于当 xlsx 被下游脚本误修改后恢复。"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.schema import Product
from analysis.normalize import products_to_df
from analysis.report import write_products_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("rebuild")


def rebuild(platform: str, since: str):
    raw_dir = ROOT / "data/raw" / platform
    if not raw_dir.exists():
        log.warning(f"no raw dir for {platform}")
        return
    since_ts = datetime.strptime(since, "%Y%m%d").timestamp()
    items = []
    files = 0
    for fp in sorted(raw_dir.glob("search_*.json")):
        if fp.stat().st_mtime < since_ts:
            continue
        files += 1
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            for raw in data:
                try:
                    items.append(Product(**raw))
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"skip {fp.name}: {e}")

    log.info(f"[{platform}] loaded {len(items)} products from {files} raw files (since {since})")
    if not items:
        return
    df = products_to_df(items)
    out = ROOT / "data/processed" / f"products_{platform}.xlsx"
    write_products_master(df, out)
    log.info(f"[{platform}] wrote {len(df)} -> {out.name}")


if __name__ == "__main__":
    platform = sys.argv[1] if len(sys.argv) > 1 else "ebay"
    since = sys.argv[2] if len(sys.argv) > 2 else "20260422"
    rebuild(platform, since)
