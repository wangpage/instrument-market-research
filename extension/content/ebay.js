// eBay search 页 content script
(async () => {
  const C = window.__scraperCommon;

  async function scrape() {
    await C.waitFor(".s-card, li.s-item", 10000);
    await C.autoScroll(3, 700);

    const cards = document.querySelectorAll(".s-card, li.s-item");
    const products = [];
    for (const card of cards) {
      // 真实 item id
      let itemId = card.getAttribute("data-listingid");
      const linkEl = card.querySelector("a.s-card__link, a.s-item__link");
      const href = linkEl ? linkEl.getAttribute("href") : null;
      if (!itemId && href) {
        const m = href.match(/\/itm\/(\d{10,})/);
        if (m) itemId = m[1];
      }
      if (!itemId || itemId === "123456") continue;

      // title: img alt 最干净
      let title = null;
      const imgEl = card.querySelector("img.s-card__image, .s-item__image img, img");
      if (imgEl && imgEl.getAttribute("alt")) title = imgEl.getAttribute("alt").trim();
      if (!title) {
        const t = card.querySelector(".s-card__title, .s-item__title, [class*='title']");
        if (t) title = t.textContent.trim();
      }
      if (!title || /Shop on eBay/i.test(title)) continue;

      const priceEl = card.querySelector(".s-card__price, .s-item__price, [class*='price']");
      const price_raw = priceEl ? priceEl.textContent.trim() : null;
      const price_usd = C.parsePrice(price_raw);

      // sold count
      let sold_count_text = null;
      for (const el of card.querySelectorAll("span, div")) {
        const t = el.textContent || "";
        if (/\d+[\d,.]*\s*sold\b/i.test(t) && t.length < 40) {
          sold_count_text = t.trim();
          break;
        }
      }

      const locEl = card.querySelector(".s-card__location, .s-item__location, .s-item__itemLocation");
      const seller_country = locEl ? locEl.textContent.trim() : null;

      products.push({
        asin_or_sku: String(itemId),
        title,
        url: href ? href.split("?")[0] : `https://www.ebay.com/itm/${itemId}`,
        image_url: imgEl ? imgEl.getAttribute("src") : null,
        price_usd, price_raw,
        currency_raw: "USD",
        sold_count_text,
        sold_count_estimated: C.parseInt10(sold_count_text),
        seller_country,
      });
    }
    return products;
  }

  const task = await C.getCurrentTask();
  const params = new URLSearchParams(location.search);
  const query = params.get("_nkw") || (task && task.query);
  if (!query) return;

  const products = await scrape();
  if (products.length) {
    await C.sendBatch("ebay", query, task, products);
    console.log(`[ebay] scraped ${products.length}`);
  }

  chrome.runtime.onMessage.addListener((msg, _, sendResponse) => {
    if (msg.type === "SCRAPE_NOW") {
      scrape().then(async (ps) => {
        await C.sendBatch("ebay", query, task, ps);
        sendResponse({ count: ps.length });
      });
      return true;
    }
  });
})();
