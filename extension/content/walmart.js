// Walmart search 页 content script — 从 __NEXT_DATA__ 读结构化数据
(async () => {
  const C = window.__scraperCommon;

  async function scrape() {
    await C.waitFor("#__NEXT_DATA__", 15000);
    await C.autoScroll(2, 500);

    const scriptEl = document.getElementById("__NEXT_DATA__");
    if (!scriptEl) return [];
    let data;
    try { data = JSON.parse(scriptEl.textContent); } catch { return []; }

    // path: props.pageProps.initialData.searchResult.itemStacks[0].items
    const items = (((((((data.props || {}).pageProps || {}).initialData || {}).searchResult || {}).itemStacks || [])[0]) || {}).items || [];
    const products = [];
    for (const it of items) {
      if (!it || typeof it !== "object") continue;
      const sku = it.usItemId || it.id || it.itemId;
      const name = it.name || it.title;
      if (!sku || !name) continue;

      const price_raw = ((it.priceInfo || {}).linePrice || (it.priceInfo || {}).itemPrice || "");
      const price_usd = C.parsePrice(price_raw);
      const was_raw = (it.priceInfo || {}).wasPrice || "";
      const original_price_usd = C.parsePrice(was_raw);

      let rating = it.averageRating;
      if (typeof rating === "string") rating = parseFloat(rating);
      let review_count = it.numberOfReviews;
      if (typeof review_count === "string") review_count = parseInt(review_count, 10);

      const url = it.canonicalUrl || it.productPageUrl || "";
      const brand = it.brand || ((it.seller || {}).name || null);

      products.push({
        asin_or_sku: String(sku),
        title: name, brand,
        url: url.startsWith("http") ? url : `https://www.walmart.com${url}`,
        image_url: ((it.imageInfo || {}).thumbnailUrl) || it.imageUrl || null,
        price_usd, price_raw,
        original_price_usd,
        currency_raw: "USD",
        rating: (typeof rating === "number" && !isNaN(rating)) ? rating : null,
        review_count: (typeof review_count === "number" && !isNaN(review_count)) ? review_count : null,
        sold_count_estimated: review_count ? Math.round(review_count / 0.02) : null,
        seller_name: (it.seller || {}).name || null,
      });
    }
    return products;
  }

  const task = await C.getCurrentTask();
  const params = new URLSearchParams(location.search);
  const query = params.get("q") || (task && task.query);
  if (!query) return;

  // 如果被 PerimeterX 重定向到 /blocked，跳过（popup 里提示）
  if (location.pathname.includes("/blocked")) {
    console.warn("[walmart] PerimeterX blocked, skip");
    // 通知 background 跳到下一个任务
    await C.sendBatch("walmart", query, task, []);
    return;
  }

  const products = await scrape();
  if (products.length) {
    await C.sendBatch("walmart", query, task, products);
    console.log(`[walmart] scraped ${products.length}`);
  } else {
    // 即使空也通知，好让 background 跳下一个
    await C.sendBatch("walmart", query, task, []);
  }

  chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
    if (msg.type === "SCRAPE_NOW") {
      scrape().then(async (ps) => {
        await C.sendBatch("walmart", query, task, ps);
        sendResponse({ count: ps.length });
      });
      return true;
    }
  });
})();
