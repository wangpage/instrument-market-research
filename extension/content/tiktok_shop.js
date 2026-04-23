// TikTok Shop search 页 content script
(async () => {
  const C = window.__scraperCommon;

  async function scrape() {
    // TikTok shop 可能返回 account region error
    if (/shop is not currently available/i.test(document.body.innerText)) {
      console.warn("[tiktok_shop] account region not US");
      return [];
    }
    await C.waitFor('a[href*="/shop/pdp/"]', 20000);
    await C.autoScroll(8, 1200);

    const seen = new Set();
    const products = [];
    for (const a of document.querySelectorAll('a[href*="/shop/pdp/"]')) {
      const href = a.getAttribute("href") || "";
      const m = href.match(/\/shop\/pdp\/[^\/]+\/(\d+)/);
      if (!m) continue;
      const pid = m[1];
      if (seen.has(pid)) continue;
      seen.add(pid);

      // title
      const img = a.querySelector("img");
      let title = img ? (img.getAttribute("alt") || "").trim() : "";
      if (!title) {
        const t = a.querySelector("p, span[data-e2e*='title'], div[data-e2e*='title']");
        title = t ? t.textContent.trim() : a.textContent.trim().slice(0, 150);
      }

      // price / sold
      let price_raw = null, sold_count_text = null;
      const txt = a.textContent || "";
      const pm = txt.match(/\$\s*[\d,.]+/);
      if (pm) price_raw = pm[0];
      const sm = txt.match(/([\d,.]+[Kk]?)\s*sold/i);
      if (sm) sold_count_text = sm[0];

      products.push({
        asin_or_sku: String(pid),
        title: title.slice(0, 300),
        url: href.startsWith("http") ? href : `https://www.tiktok.com${href}`,
        image_url: img ? img.getAttribute("src") : null,
        price_usd: C.parsePrice(price_raw),
        price_raw,
        currency_raw: "USD",
        sold_count_text,
        sold_count_estimated: C.parseInt10(sold_count_text),
      });
    }
    return products;
  }

  const task = await C.getCurrentTask();
  const m = location.pathname.match(/\/shop\/s\/([^\/]+)/);
  const query = m ? decodeURIComponent(m[1]) : (task && task.query);
  if (!query) return;

  const products = await scrape();
  await C.sendBatch("tiktok_shop", query, task, products);
  console.log(`[tiktok_shop] scraped ${products.length}`);

  chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
    if (msg.type === "SCRAPE_NOW") {
      scrape().then(async (ps) => {
        await C.sendBatch("tiktok_shop", query, task, ps);
        sendResponse({ count: ps.length });
      });
      return true;
    }
  });
})();
