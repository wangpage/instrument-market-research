// Temu search 页 content script
(async () => {
  const C = window.__scraperCommon;

  async function scrape() {
    // Temu 是 SPA 懒加载，要等 + 滚动触发渲染
    await C.waitFor("a[href*='-g-']", 15000);
    await C.autoScroll(6, 1000);

    const seen = new Set();
    const products = [];
    for (const a of document.querySelectorAll("a[href*='-g-']")) {
      const href = a.getAttribute("href") || "";
      const m = href.match(/-g-(\d+)\.html/);
      if (!m) continue;
      const gid = m.group ? m.group(1) : m[1];
      if (seen.has(gid)) continue;
      seen.add(gid);

      // title: img alt
      const img = a.querySelector("img");
      let title = img ? (img.getAttribute("alt") || "").trim() : "";
      if (!title || title === "image" || title === "img") {
        // slug 反推
        const sm = href.match(/\/([^\/]+)-g-\d+\.html/);
        title = sm ? decodeURIComponent(sm[1].replace(/-/g, " ")) : "";
      }

      // price: 往父层找 $xxx
      let price_raw = null;
      let container = a;
      for (let i = 0; i < 4 && container; i++) {
        const txt = container.textContent || "";
        const pm = txt.match(/\$\s*[\d,.]+/);
        if (pm) { price_raw = pm[0]; break; }
        container = container.parentElement;
      }
      const price_usd = C.parsePrice(price_raw);

      // sold
      let sold_count_text = null;
      if (container) {
        const txt = container.textContent || "";
        const sm = txt.match(/([\d,.]+[Kk]?\+?)\s*sold/i);
        if (sm) sold_count_text = sm[0];
      }

      products.push({
        asin_or_sku: String(gid),
        title: title.slice(0, 300),
        url: href.startsWith("http") ? href : `https://www.temu.com${href}`,
        image_url: img ? (img.getAttribute("src") || img.getAttribute("data-src")) : null,
        price_usd, price_raw,
        currency_raw: "USD",
        sold_count_text,
        sold_count_estimated: C.parseInt10(sold_count_text),
      });
    }
    return products;
  }

  const task = await C.getCurrentTask();
  const params = new URLSearchParams(location.search);
  const query = params.get("search_key") || (task && task.query);
  if (!query) return;

  const products = await scrape();
  await C.sendBatch("temu", query, task, products);
  console.log(`[temu] scraped ${products.length}`);

  chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
    if (msg.type === "SCRAPE_NOW") {
      scrape().then(async (ps) => {
        await C.sendBatch("temu", query, task, ps);
        sendResponse({ count: ps.length });
      });
      return true;
    }
  });
})();
