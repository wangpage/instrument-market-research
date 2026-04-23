"""
不需要装扩展：用 CDP 打开真实 Chrome 页面，把 content script 的 scrape 函数
直接 page.evaluate 注入执行，拿回商品数据。

本质上和扩展一样（都是读渲染后的 DOM），但全程 Python 自动化。
"""
import asyncio
import json
import os
import sys
import logging
from pathlib import Path
from urllib.parse import quote

os.environ["BROWSER_MODE"] = "cdp"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright
from config.keywords import all_queries, queries_for_subcategory
from config.schema import Product
from analysis.normalize import products_to_df
from analysis.report import write_products_master

ROOT = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("inject")


# —— 每个平台的 URL 构造 + JS 注入函数 ——
def build_url(platform, query):
    q = quote(query, safe="")
    return {
        "amazon": f"https://www.amazon.com/s?k={q}",
        "ebay": f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_BIN=1&LH_PrefLoc=1",
        "walmart": f"https://www.walmart.com/search?q={q}",
        "temu": f"https://www.temu.com/search_result.html?search_key={q}&search_method=user",
        "tiktok_shop": f"https://www.tiktok.com/shop/s/{q}",
    }.get(platform)


# —— JS 注入代码（等价于扩展 content script）——

AMAZON_JS = r"""
async () => {
  // 自动滚动
  for (let i = 0; i < 3; i++) { window.scrollBy(0, 800); await new Promise(r => setTimeout(r, 700)); }
  const parsePrice = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/[\$€£¥]?\s*(\d+(?:\.\d+)?)/); return m?parseFloat(m[1]):null; };
  const out = [];
  for (const card of document.querySelectorAll("div.s-result-item[data-asin]")) {
    const asin = card.getAttribute("data-asin");
    if (!asin || asin.length < 10) continue;
    const titleEl = card.querySelector("h2 span");
    if (!titleEl) continue;
    const title = titleEl.textContent.trim();
    const linkEl = card.querySelector("h2 a");
    const href = linkEl ? linkEl.getAttribute("href") : null;
    const url = href ? new URL(href, location.origin).href : `https://www.amazon.com/dp/${asin}`;
    const priceEl = card.querySelector("span.a-price span.a-offscreen");
    const price_raw = priceEl ? priceEl.textContent.trim() : null;
    let rating=null, review_count=null;
    for (const el of card.querySelectorAll("[aria-label]")) {
      const lbl = el.getAttribute("aria-label") || "";
      if (/out of 5 stars by/.test(lbl)) {
        const m = lbl.match(/Rated\s+([\d.]+)\s+out of 5 stars by\s+([\d,]+)/);
        if (m) { rating = parseFloat(m[1]); review_count = parseInt(m[2].replace(/,/g,''),10); break; }
      }
      if (rating===null && /out of 5 stars/.test(lbl)) {
        const m = lbl.match(/([\d.]+)\s+out of 5 stars/); if (m) rating = parseFloat(m[1]);
      }
      if (review_count===null && /^[\d,]+\s+ratings?$/.test(lbl.trim())) {
        review_count = parseInt(lbl.replace(/,/g,'').trim(), 10);
      }
    }
    const img = card.querySelector("img.s-image");
    out.push({
      asin_or_sku: asin, title, url, image_url: img?img.getAttribute("src"):null,
      price_usd: parsePrice(price_raw), price_raw, currency_raw: "USD",
      rating, review_count,
      sold_count_estimated: review_count ? Math.round(review_count/0.02) : null,
    });
  }
  return out;
}
"""

EBAY_JS = r"""
async () => {
  for (let i = 0; i < 3; i++) { window.scrollBy(0, 800); await new Promise(r => setTimeout(r, 700)); }
  const parsePrice = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/[\$€£¥]?\s*(\d+(?:\.\d+)?)/); return m?parseFloat(m[1]):null; };
  const parseInt10 = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/(\d+)/); return m?parseInt(m[1],10):null; };
  const out = [];
  for (const card of document.querySelectorAll(".s-card, li.s-item")) {
    let itemId = card.getAttribute("data-listingid");
    const linkEl = card.querySelector("a.s-card__link, a.s-item__link");
    const href = linkEl ? linkEl.getAttribute("href") : null;
    if (!itemId && href) { const m = href.match(/\/itm\/(\d{10,})/); if (m) itemId = m[1]; }
    if (!itemId || itemId === "123456") continue;
    let title = null;
    const img = card.querySelector("img.s-card__image, .s-item__image img, img");
    if (img && img.getAttribute("alt")) title = img.getAttribute("alt").trim();
    if (!title) {
      const t = card.querySelector(".s-card__title, .s-item__title");
      if (t) title = t.textContent.trim();
    }
    if (!title || /Shop on eBay/i.test(title)) continue;
    const priceEl = card.querySelector(".s-card__price, .s-item__price");
    const price_raw = priceEl ? priceEl.textContent.trim() : null;
    let sold_count_text = null;
    for (const el of card.querySelectorAll("span, div")) {
      const t = el.textContent || "";
      if (/\d+[\d,.]*\s*sold\b/i.test(t) && t.length < 40) { sold_count_text = t.trim(); break; }
    }
    out.push({
      asin_or_sku: String(itemId), title,
      url: href ? href.split("?")[0] : `https://www.ebay.com/itm/${itemId}`,
      image_url: img ? img.getAttribute("src") : null,
      price_usd: parsePrice(price_raw), price_raw, currency_raw: "USD",
      sold_count_text, sold_count_estimated: parseInt10(sold_count_text),
    });
  }
  return out;
}
"""

WALMART_JS = r"""
async () => {
  // 等 __NEXT_DATA__
  for (let i=0; i<20 && !document.getElementById('__NEXT_DATA__'); i++) await new Promise(r=>setTimeout(r,500));
  for (let i=0; i<2; i++) { window.scrollBy(0,800); await new Promise(r=>setTimeout(r,500)); }
  const el = document.getElementById("__NEXT_DATA__");
  if (!el) return [];
  let data; try { data = JSON.parse(el.textContent); } catch { return []; }
  const items = (((((((data.props||{}).pageProps||{}).initialData||{}).searchResult||{}).itemStacks||[])[0])||{}).items||[];
  const parsePrice = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/[\$€£¥]?\s*(\d+(?:\.\d+)?)/); return m?parseFloat(m[1]):null; };
  const out = [];
  for (const it of items) {
    if (!it || typeof it !== "object") continue;
    const sku = it.usItemId || it.id || it.itemId;
    const name = it.name || it.title;
    if (!sku || !name) continue;
    const price_raw = ((it.priceInfo||{}).linePrice || (it.priceInfo||{}).itemPrice || "");
    let rating = it.averageRating; if (typeof rating === "string") rating = parseFloat(rating);
    let rc = it.numberOfReviews; if (typeof rc === "string") rc = parseInt(rc, 10);
    const url = it.canonicalUrl || it.productPageUrl || "";
    out.push({
      asin_or_sku: String(sku), title: name, brand: it.brand || null,
      url: url.startsWith("http") ? url : `https://www.walmart.com${url}`,
      image_url: ((it.imageInfo||{}).thumbnailUrl) || it.imageUrl || null,
      price_usd: parsePrice(price_raw), price_raw, currency_raw: "USD",
      original_price_usd: parsePrice((it.priceInfo||{}).wasPrice || ""),
      rating: (typeof rating === "number" && !isNaN(rating)) ? rating : null,
      review_count: (typeof rc === "number" && !isNaN(rc)) ? rc : null,
      sold_count_estimated: rc ? Math.round(rc/0.02) : null,
      seller_name: (it.seller||{}).name || null,
    });
  }
  return out;
}
"""

TEMU_JS = r"""
async () => {
  // 等商品链接
  for (let i=0; i<30 && !document.querySelector("a[href*='-g-']"); i++) await new Promise(r=>setTimeout(r,500));
  for (let i=0; i<6; i++) { window.scrollBy(0, 800); await new Promise(r=>setTimeout(r, 900)); }
  const parsePrice = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/[\$€£¥]?\s*(\d+(?:\.\d+)?)/); return m?parseFloat(m[1]):null; };
  const parseInt10 = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/(\d+)/); return m?parseInt(m[1],10):null; };
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll("a[href*='-g-']")) {
    const href = a.getAttribute("href") || "";
    const m = href.match(/-g-(\d+)\.html/);
    if (!m) continue;
    const gid = m[1];
    if (seen.has(gid)) continue;
    seen.add(gid);
    const img = a.querySelector("img");
    let title = img ? (img.getAttribute("alt") || "").trim() : "";
    if (!title || title === "image" || title === "img") {
      const sm = href.match(/\/([^\/]+)-g-\d+\.html/);
      title = sm ? decodeURIComponent(sm[1].replace(/-/g, " ")) : "";
    }
    let price_raw = null, container = a;
    for (let i = 0; i < 4 && container; i++) {
      const txt = container.textContent || "";
      const pm = txt.match(/\$\s*[\d,.]+/);
      if (pm) { price_raw = pm[0]; break; }
      container = container.parentElement;
    }
    let sold_count_text = null;
    if (container) {
      const sm = (container.textContent || "").match(/([\d,.]+[Kk]?\+?)\s*sold/i);
      if (sm) sold_count_text = sm[0];
    }
    out.push({
      asin_or_sku: String(gid), title: title.slice(0, 300),
      url: href.startsWith("http") ? href : `https://www.temu.com${href}`,
      image_url: img ? (img.getAttribute("src") || img.getAttribute("data-src")) : null,
      price_usd: parsePrice(price_raw), price_raw, currency_raw: "USD",
      sold_count_text, sold_count_estimated: parseInt10(sold_count_text),
    });
  }
  return out;
}
"""

TIKTOK_JS = r"""
async () => {
  if (/shop is not currently available/i.test(document.body.innerText)) return { __error: "account_region_blocked" };
  for (let i=0; i<40 && !document.querySelector('a[href*="/shop/pdp/"]'); i++) await new Promise(r=>setTimeout(r,500));
  for (let i=0; i<10; i++) { window.scrollBy(0, 800); await new Promise(r=>setTimeout(r, 1000)); }
  const parsePrice = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/[\$€£¥]?\s*(\d+(?:\.\d+)?)/); return m?parseFloat(m[1]):null; };
  const parseInt10 = t => { if(!t) return null; const m=String(t).replace(/,/g,'').match(/(\d+)/); return m?parseInt(m[1],10):null; };
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll('a[href*="/shop/pdp/"]')) {
    const href = a.getAttribute("href") || "";
    const m = href.match(/\/shop\/pdp\/[^\/]+\/(\d+)/);
    if (!m) continue;
    const pid = m[1]; if (seen.has(pid)) continue; seen.add(pid);
    const img = a.querySelector("img");
    let title = img ? (img.getAttribute("alt") || "").trim() : "";
    if (!title) title = a.textContent.trim().slice(0, 150);
    const txt = a.textContent || "";
    const pm = txt.match(/\$\s*[\d,.]+/);
    const sm = txt.match(/([\d,.]+[Kk]?)\s*sold/i);
    out.push({
      asin_or_sku: String(pid), title: title.slice(0, 300),
      url: href.startsWith("http") ? href : `https://www.tiktok.com${href}`,
      image_url: img ? img.getAttribute("src") : null,
      price_usd: parsePrice(pm ? pm[0] : null), price_raw: pm ? pm[0] : null,
      currency_raw: "USD",
      sold_count_text: sm ? sm[0] : null,
      sold_count_estimated: sm ? parseInt10(sm[0]) : null,
    });
  }
  return out;
}
"""

PLATFORM_JS = {
    "amazon": AMAZON_JS, "ebay": EBAY_JS, "walmart": WALMART_JS,
    "temu": TEMU_JS, "tiktok_shop": TIKTOK_JS,
}


async def run_platform(platform, only_subcategory=None, top_n=20, delay_sec=4):
    if only_subcategory:
        tasks = queries_for_subcategory(only_subcategory)
    else:
        tasks = all_queries()

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = await ctx.new_page()

    all_products = []
    for cat, sub, query, is_smart in tasks:
        url = build_url(platform, query)
        if not url:
            continue
        log.info(f"[{platform}] {query!r}")
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(delay_sec)  # 等页面稳定
            result = await page.evaluate(PLATFORM_JS[platform])
        except Exception as e:
            log.warning(f"  error: {e}")
            result = []

        if isinstance(result, dict) and result.get("__error"):
            log.warning(f"  {result['__error']}, STOP platform")
            break

        products = result or []
        for i, p in enumerate(products[:top_n]):
            all_products.append(Product(
                platform=platform,
                query_keyword=query,
                category=cat,
                subcategory=sub,
                rank_in_search=i + 1,
                is_smart_instrument=is_smart,
                **{k: v for k, v in p.items() if k in Product.model_fields},
            ))
        log.info(f"  got {len(products)} (keep top {min(len(products), top_n)})")
        await asyncio.sleep(2)

    await page.close()
    await pw.stop()

    df = products_to_df(all_products)
    out = ROOT / "data" / "processed" / f"products_{platform}.xlsx"
    if not df.empty:
        write_products_master(df, out)
        log.info(f"saved {len(df)} unique products → {out}")
    else:
        log.warning("no products captured")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--platform", required=True, choices=list(PLATFORM_JS))
    p.add_argument("--subcategory", default=None)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--delay", type=float, default=4.0)
    args = p.parse_args()
    asyncio.run(run_platform(args.platform, args.subcategory, args.top_n, args.delay))
