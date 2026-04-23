// Amazon search 页 content script — 从 DOM 抽商品
(async () => {
  const C = window.__scraperCommon;

  async function scrape() {
    await C.waitFor("div.s-result-item[data-asin]", 10000);
    await C.autoScroll(3, 700);

    const cards = document.querySelectorAll("div.s-result-item[data-asin]");
    const products = [];
    for (const card of cards) {
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
      const price_usd = C.parsePrice(price_raw);

      // rating + review count — 两种布局
      let rating = null, review_count = null;
      for (const el of card.querySelectorAll("[aria-label]")) {
        const lbl = el.getAttribute("aria-label") || "";
        if (/out of 5 stars by/.test(lbl)) {
          const m = lbl.match(/Rated\s+([\d.]+)\s+out of 5 stars by\s+([\d,]+)/);
          if (m) { rating = parseFloat(m[1]); review_count = parseInt(m[2].replace(/,/g, ""), 10); break; }
        }
        if (rating === null && /out of 5 stars/.test(lbl)) {
          const m = lbl.match(/([\d.]+)\s+out of 5 stars/);
          if (m) rating = parseFloat(m[1]);
        }
        if (review_count === null && /^[\d,]+\s+ratings?$/.test(lbl.trim())) {
          review_count = parseInt(lbl.replace(/,/g, "").trim(), 10);
        }
      }

      const imgEl = card.querySelector("img.s-image");
      const image_url = imgEl ? imgEl.getAttribute("src") : null;

      products.push({
        asin_or_sku: asin,
        title, url, image_url,
        price_usd, price_raw,
        currency_raw: "USD",
        rating, review_count,
        sold_count_estimated: review_count ? Math.round(review_count / 0.02) : null,
      });
    }
    return products;
  }

  // 批量模式：URL 里的 query 参数对应
  const task = await C.getCurrentTask();
  const params = new URLSearchParams(location.search);
  const query = params.get("k") || (task && task.query);
  if (!query) return;

  const products = await scrape();
  if (products.length) {
    await C.sendBatch("amazon", query, task, products);
    console.log(`[amazon] scraped ${products.length}`);
  }

  // 手动模式响应
  chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
    if (msg.type === "SCRAPE_NOW") {
      scrape().then(async (ps) => {
        await C.sendBatch("amazon", query, task, ps);
        sendResponse({ count: ps.length });
      });
      return true;
    }
  });
})();
