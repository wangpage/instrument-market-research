// 协调者：接收 content script 发来的商品数据 + 管理批量任务队列

const STORAGE_KEY = "scraped_products";
const QUEUE_KEY = "scrape_queue";

// 初始化存储
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get([STORAGE_KEY], (r) => {
    if (!r[STORAGE_KEY]) {
      chrome.storage.local.set({ [STORAGE_KEY]: [] });
    }
  });
});

// 接收来自 content script 的商品数据
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "SCRAPED_BATCH") {
    // msg.products: [{platform, query, title, price_usd, ...}]
    chrome.storage.local.get([STORAGE_KEY], (r) => {
      const all = r[STORAGE_KEY] || [];
      all.push(...msg.products);
      chrome.storage.local.set({ [STORAGE_KEY]: all }, () => {
        console.log(`[bg] +${msg.products.length} from ${msg.platform}/${msg.query}, total=${all.length}`);
        sendResponse({ ok: true, total: all.length });
        // 告知下一个任务
        processNext();
      });
    });
    return true; // 异步 response
  }
  if (msg.type === "GET_STATE") {
    chrome.storage.local.get([STORAGE_KEY, QUEUE_KEY], (r) => {
      sendResponse({
        products: r[STORAGE_KEY] || [],
        queue: r[QUEUE_KEY] || [],
      });
    });
    return true;
  }
  if (msg.type === "START_BATCH") {
    // msg.tasks: [{platform, query, category, subcategory, is_smart}, ...]
    chrome.storage.local.set({ [QUEUE_KEY]: msg.tasks }, () => {
      processNext();
      sendResponse({ ok: true, queued: msg.tasks.length });
    });
    return true;
  }
  if (msg.type === "CLEAR_DATA") {
    chrome.storage.local.set({ [STORAGE_KEY]: [], [QUEUE_KEY]: [] }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }
  if (msg.type === "EXPORT_CSV") {
    chrome.storage.local.get([STORAGE_KEY], (r) => {
      const rows = r[STORAGE_KEY] || [];
      const csv = toCSV(rows);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const reader = new FileReader();
      reader.onload = () => {
        chrome.downloads.download({
          url: reader.result,
          filename: `products_${Date.now()}.csv`,
          saveAs: true,
        });
      };
      reader.readAsDataURL(blob);
      sendResponse({ ok: true, rows: rows.length });
    });
    return true;
  }
  if (msg.type === "EXPORT_JSON") {
    chrome.storage.local.get([STORAGE_KEY], (r) => {
      const rows = r[STORAGE_KEY] || [];
      const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
      const reader = new FileReader();
      reader.onload = () => {
        chrome.downloads.download({
          url: reader.result,
          filename: `products_${Date.now()}.json`,
          saveAs: true,
        });
      };
      reader.readAsDataURL(blob);
      sendResponse({ ok: true, rows: rows.length });
    });
    return true;
  }
});

// 从队列拿下一个任务，打开对应 URL
async function processNext() {
  const r = await chrome.storage.local.get([QUEUE_KEY]);
  const queue = r[QUEUE_KEY] || [];
  if (!queue.length) {
    console.log("[bg] queue empty");
    return;
  }
  const task = queue[0];
  const rest = queue.slice(1);
  await chrome.storage.local.set({ [QUEUE_KEY]: rest });

  const url = buildSearchUrl(task.platform, task.query);
  if (!url) {
    console.warn("[bg] unknown platform", task.platform);
    return processNext();
  }
  // 把 task 元信息放到 session（content script 读取）
  await chrome.storage.session.set({
    current_task: task,
  });
  // 先找已有 tab 复用，否则开新 tab
  const tabs = await chrome.tabs.query({ url: [
    "https://www.amazon.com/*",
    "https://www.ebay.com/*",
    "https://www.walmart.com/*",
    "https://www.temu.com/*",
    "https://www.tiktok.com/*",
  ] });
  if (tabs.length > 0) {
    await chrome.tabs.update(tabs[0].id, { url, active: true });
  } else {
    await chrome.tabs.create({ url, active: true });
  }
}

function buildSearchUrl(platform, query) {
  const q = encodeURIComponent(query);
  const q20 = q.replace(/\+/g, "%20"); // 某些平台不接受 +
  switch (platform) {
    case "amazon":
      return `https://www.amazon.com/s?k=${q}`;
    case "ebay":
      return `https://www.ebay.com/sch/i.html?_nkw=${q}&LH_BIN=1&LH_PrefLoc=1`;
    case "walmart":
      return `https://www.walmart.com/search?q=${q}`;
    case "temu":
      return `https://www.temu.com/search_result.html?search_key=${q20}&search_method=user`;
    case "tiktok_shop":
      return `https://www.tiktok.com/shop/s/${q20}`;
    default:
      return null;
  }
}

function toCSV(rows) {
  if (!rows.length) return "";
  const cols = [
    "platform", "query_keyword", "category", "subcategory", "rank_in_search",
    "title", "brand", "asin_or_sku", "url", "image_url",
    "price_usd", "original_price_usd", "currency_raw", "price_raw",
    "rating", "review_count", "sold_count_text", "sold_count_estimated",
    "seller_name", "seller_country", "is_smart_instrument", "scraped_at",
  ];
  const esc = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v).replace(/"/g, '""');
    return /[",\n]/.test(s) ? `"${s}"` : s;
  };
  return [cols.join(",")]
    .concat(rows.map((r) => cols.map((c) => esc(r[c])).join(",")))
    .join("\n");
}
