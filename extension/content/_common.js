// 共享工具（每个 content script 在 IIFE 里复制这些函数）
// Content script 用 ISOLATED world 不能直接 import，所以用 self-contained 函数

window.__scraperCommon = {
  // 等 DOM 里出现某个 selector 或超时
  waitFor: async (selector, timeoutMs = 8000) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (document.querySelector(selector)) return document.querySelector(selector);
      await new Promise((r) => setTimeout(r, 300));
    }
    return null;
  },

  // 自动滚动触发懒加载
  autoScroll: async (steps = 6, delayMs = 900) => {
    for (let i = 0; i < steps; i++) {
      window.scrollBy(0, 800);
      await new Promise((r) => setTimeout(r, delayMs));
    }
  },

  // 从字符串里抠出第一个数字
  parsePrice: (text) => {
    if (!text) return null;
    const m = String(text).replace(/,/g, "").match(/[\$€£¥]?\s*(\d+(?:\.\d+)?)/);
    return m ? parseFloat(m[1]) : null;
  },
  parseInt10: (text) => {
    if (!text) return null;
    const m = String(text).replace(/,/g, "").match(/(\d+)/);
    return m ? parseInt(m[1], 10) : null;
  },

  // 发送一批到 background
  sendBatch: async (platform, query, task, products) => {
    return chrome.runtime.sendMessage({
      type: "SCRAPED_BATCH",
      platform,
      query,
      products: products.map((p, i) => ({
        platform,
        query_keyword: query,
        category: task?.category || "unknown",
        subcategory: task?.subcategory || "unknown",
        is_smart_instrument: !!task?.is_smart,
        rank_in_search: i + 1,
        scraped_at: new Date().toISOString(),
        ...p,
      })),
    });
  },

  // 从 sessionStorage（跨页保留）读当前任务元信息
  getCurrentTask: async () => {
    try {
      const r = await chrome.storage.session.get(["current_task"]);
      return r.current_task || null;
    } catch {
      return null;
    }
  },
};
