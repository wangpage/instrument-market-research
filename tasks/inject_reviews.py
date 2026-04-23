"""
评论抓取器：从 master Excel 读 Top N SKU（按 review_count 排序），
用 CDP Chrome 打开详情页 → 注入 JS 抽评论文本 → 存 Excel。

评论本身原文保留，后续可人工或让 Claude 分析好评/吐槽聚类。
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
import pandas as pd

os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright
from config.schema import Review

ROOT = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("rev")


def build_review_url(platform, sku, product_url=None):
    return {
        # Amazon 评论页强制登录，改用商品主页底部的 top reviews
        "amazon": f"https://www.amazon.com/dp/{sku}",
        "walmart": f"https://www.walmart.com/reviews/product/{sku}",
        # Temu 需要完整商品 URL，goods_id 单独不够
        "temu": product_url if product_url else f"https://www.temu.com/goods.html?goods_id={sku}",
        "ebay": f"https://www.ebay.com/itm/{sku}",
        "tiktok_shop": f"https://www.tiktok.com/shop/pdp/{sku}",
    }.get(platform)


AMAZON_REV_JS = r"""
async () => {
  // 从商品主页 /dp/{asin} 抓底部 Top reviews（不用登录）
  // 先滚到评论区触发懒加载
  for (let i=0; i<8; i++) { window.scrollBy(0, 800); await new Promise(r=>setTimeout(r, 500)); }
  if (/signin|Sign-In/i.test(document.title)) return { __error: "amazon_login_required" };
  if (/captcha|Robot Check/i.test(document.title)) return { __error: "amazon_captcha" };
  const out = [];
  // 主页顶部可能只有 3-5 条 top reviews
  for (const b of document.querySelectorAll("div[data-hook='review'], li[data-hook='review']")) {
    const rid = b.id || `az_${out.length}`;
    const rEl = b.querySelector("i[data-hook*='review-star-rating'] span, i[data-hook='cmps-review-star-rating'] span");
    let rating = null;
    if (rEl) { const m = rEl.textContent.match(/([\d.]+)/); if (m) rating = parseFloat(m[1]); }
    const tEl = b.querySelector("a[data-hook='review-title'], span[data-hook='review-title']");
    const title = tEl ? tEl.textContent.trim() : null;
    const bodyEl = b.querySelector("span[data-hook='review-body']");
    const body = bodyEl ? bodyEl.textContent.trim() : "";
    const dateEl = b.querySelector("span[data-hook='review-date']");
    const date = dateEl ? dateEl.textContent.trim() : null;
    const verified = !!b.querySelector("span[data-hook='avp-badge']");
    out.push({ review_id: rid, rating, date, title, body, verified_purchase: verified });
  }
  // 补充：Amazon 新版把 "Customer says" 放在商品主页顶部
  const csEl = document.querySelector("#customer-reviews-content [data-hook='cr-insights-widget-summary'], [cel_widget_id*='product-insights']");
  if (csEl) {
    const summary = csEl.innerText.trim();
    if (summary && summary.length > 50) {
      out.push({ review_id: "amazon_customer_says", title: "Customer says (AI summary)", body: summary.slice(0, 2000), rating: null });
    }
  }
  return out;
}
"""

WALMART_REV_JS = r"""
async () => {
  for (let i=0; i<20 && !document.getElementById('__NEXT_DATA__'); i++) await new Promise(r=>setTimeout(r, 500));
  for (let i=0; i<4; i++) { window.scrollBy(0, 800); await new Promise(r=>setTimeout(r, 600)); }
  const el = document.getElementById("__NEXT_DATA__");
  if (!el) return [];
  let data; try { data = JSON.parse(el.textContent); } catch { return []; }
  // reviews 路径: pageProps.initialData.data.reviews.customerReviews
  function dig(obj, path) {
    for (const k of path) {
      if (obj == null) return null;
      obj = obj[k];
    }
    return obj;
  }
  let revs = dig(data, ["props","pageProps","initialData","data","reviews","customerReviews"])
           || dig(data, ["props","pageProps","initialData","reviews","customerReviews"])
           || [];
  if (!Array.isArray(revs)) return [];
  return revs.map((rv, i) => ({
    review_id: rv.reviewId || rv.id || `wm_${i}`,
    author: rv.userNickname || ((rv.reviewer||{}).nickname),
    rating: rv.rating,
    date: rv.submissionTime || rv.reviewSubmissionTime,
    title: rv.reviewTitle,
    body: rv.reviewText || "",
    helpful_count: rv.positiveFeedback,
  }));
}
"""

TEMU_REV_JS = r"""
async () => {
  for (let i=0; i<8; i++) { window.scrollBy(0, 800); await new Promise(r=>setTimeout(r, 800)); }
  // Temu 评论区 class 名变化多，抓 review 相关 div
  const out = [];
  const cards = document.querySelectorAll("[class*='omment' i], [class*='eview' i]");
  let i = 0;
  const seen = new Set();
  for (const c of cards) {
    const text = (c.innerText || "").trim();
    if (text.length < 15 || text.length > 2000) continue;
    if (seen.has(text.slice(0, 50))) continue;
    seen.add(text.slice(0, 50));
    // rating: star icon
    let rating = null;
    const stars = c.querySelectorAll("[class*='star' i][class*='filled' i], [class*='star' i][class*='active' i]");
    if (stars.length > 0 && stars.length <= 5) rating = stars.length;
    out.push({ review_id: `tm_${i++}`, body: text.slice(0, 1500), rating });
    if (out.length >= 30) break;
  }
  return out;
}
"""

PLATFORM_REV_JS = {
    "amazon": AMAZON_REV_JS,
    "walmart": WALMART_REV_JS,
    "temu": TEMU_REV_JS,
}


async def main(platforms, top_k_per_platform=25, per_sku=15):
    """从 master Excel 读各平台 top SKU, 批量抓评论"""
    master = ROOT / "data/processed/products_master.xlsx"
    if not master.exists():
        log.error("products_master.xlsx missing; run build_report first")
        return
    df = pd.read_excel(master, sheet_name="all_products")
    # 按 review_count 降序；Temu 没 review_count 的用 rank_in_search 升序
    df["_sort"] = df["review_count"].fillna(-1)

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = await ctx.new_page()

    all_reviews = []
    for plat in platforms:
        if plat not in PLATFORM_REV_JS:
            log.warning(f"no review scraper for {plat}, skip")
            continue
        plat_df = df[df["platform"] == plat].copy()
        # Amazon/Walmart 按 review_count 降序；Temu 按 rank_in_search 升序
        if plat == "temu":
            plat_df = plat_df.sort_values("rank_in_search")
        else:
            plat_df = plat_df.sort_values("_sort", ascending=False)
        sub = plat_df.head(top_k_per_platform)
        log.info(f"[{plat}] fetching reviews for {len(sub)} SKUs")
        for _, row in sub.iterrows():
            sku = str(row["asin_or_sku"])
            url = build_review_url(plat, sku, product_url=row.get("url"))
            if not url:
                continue
            try:
                await page.goto(url, timeout=45000, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                result = await page.evaluate(PLATFORM_REV_JS[plat])
            except Exception as e:
                log.warning(f"  {sku}: err {e}")
                continue
            if isinstance(result, dict) and result.get("__error"):
                log.warning(f"  {sku}: {result['__error']}")
                continue
            revs = result or []
            for rv in revs[:per_sku]:
                all_reviews.append(Review(
                    platform=plat,
                    asin_or_sku=sku,
                    review_id=str(rv.get("review_id") or f"{sku}_{len(all_reviews)}"),
                    author=rv.get("author"),
                    rating=rv.get("rating"),
                    date=rv.get("date"),
                    title=rv.get("title"),
                    body=(rv.get("body") or "")[:2000],
                    helpful_count=rv.get("helpful_count"),
                    verified_purchase=rv.get("verified_purchase"),
                ))
            log.info(f"  {sku}: {len(revs)} reviews")
            await asyncio.sleep(2)

    await page.close()
    await pw.stop()

    # 写 excel — append mode：读旧 + 合并 + dedup
    from analysis.normalize import reviews_to_df
    from analysis.report import write_reviews_master
    df_new = reviews_to_df(all_reviews)
    out = ROOT / "data/processed/reviews_master.xlsx"
    if out.exists():
        try:
            df_old = pd.read_excel(out, sheet_name="all_reviews")
            df_merged = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(
                subset=["platform", "asin_or_sku", "review_id"], keep="last"
            )
            write_reviews_master(df_merged, out)
            log.info(f"appended {len(df_new)} new, total {len(df_merged)} → {out}")
            return
        except Exception as e:
            log.warning(f"append failed, overwriting: {e}")
    if not df_new.empty:
        write_reviews_master(df_new, out)
        log.info(f"wrote {len(df_new)} reviews → {out}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--platforms", default="amazon,walmart,temu")
    p.add_argument("--top-k", type=int, default=25)
    p.add_argument("--per-sku", type=int, default=15)
    args = p.parse_args()
    asyncio.run(main(args.platforms.split(","), args.top_k, args.per_sku))
