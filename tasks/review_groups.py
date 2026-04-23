"""按 SKU 把评论分组，关联商品 title/price，方便逐 SKU 分析"""
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

reviews = pd.read_excel(ROOT / "data/processed/reviews_master.xlsx")
products = pd.read_excel(ROOT / "data/processed/products_master.xlsx", sheet_name="all_products")

# 关联 sku → product info
prod_lookup = {}
for _, p in products.iterrows():
    key = (p["platform"], str(p["asin_or_sku"]))
    prod_lookup[key] = {
        "title": p.get("title"),
        "price_usd": p.get("price_usd"),
        "brand": p.get("brand"),
        "rating": p.get("rating"),
        "review_count": p.get("review_count"),
        "subcategory": p.get("subcategory"),
        "is_smart": p.get("is_smart_instrument"),
        "url": p.get("url"),
    }

groups = {}
for _, r in reviews.iterrows():
    key = (r["platform"], str(r["asin_or_sku"]))
    if key not in groups:
        groups[key] = {"info": prod_lookup.get(key, {}), "reviews": []}
    groups[key]["reviews"].append({
        "rating": r.get("rating"),
        "title": r.get("title"),
        "body": r.get("body"),
        "date": r.get("date"),
    })

# 输出 JSON（便于传给 Claude 分析）
out = []
for (platform, sku), g in groups.items():
    out.append({
        "platform": platform,
        "asin_or_sku": sku,
        "info": g["info"],
        "n_reviews": len(g["reviews"]),
        "reviews": g["reviews"],
    })

# 按评论数排序
out.sort(key=lambda x: -x["n_reviews"])
Path(ROOT / "data/processed/review_groups.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
print(f"Wrote {len(out)} SKU groups, total {sum(x['n_reviews'] for x in out)} reviews")

# 同时输出 markdown（人类看/给 Claude 看）
lines = []
for g in out[:30]:
    info = g["info"]
    lines.append(f"## {g['platform']} · {g['asin_or_sku']}  (n={g['n_reviews']} reviews)")
    lines.append(f"**Title**: {info.get('title', '?')[:200]}")
    lines.append(f"**Brand**: {info.get('brand')}  |  **Price**: ${info.get('price_usd')}  |  **Rating**: {info.get('rating')}  |  **Subcategory**: {info.get('subcategory')}")
    lines.append("")
    for i, r in enumerate(g["reviews"][:10], 1):
        body = (r.get("body") or "").strip()
        # 清理 Amazon review 里的 "X.0 out of 5 stars" 和换行
        import re
        body = re.sub(r"\s+", " ", body)
        body = re.sub(r"^[\d.]+ out of 5 stars\s*", "", body)
        lines.append(f"{i}. **★{r.get('rating')}** — {body[:300]}")
    lines.append("\n---\n")

Path(ROOT / "data/processed/review_groups.md").write_text("\n".join(lines), encoding="utf-8")
print(f"Also wrote markdown preview → review_groups.md ({sum(len(l) for l in lines)} chars)")
