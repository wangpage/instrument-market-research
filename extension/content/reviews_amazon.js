// Amazon 评论抓取（在 /product-reviews/{ASIN} 页面运行）
// 注意：此文件不在 manifest content_scripts 列表，
// 通过 popup 手动触发 chrome.scripting.executeScript 注入
(async () => {
  const getRating = (el) => {
    if (!el) return null;
    const m = (el.textContent || "").match(/([\d.]+)/);
    return m ? parseFloat(m[1]) : null;
  };
  for (let i = 0; i < 3; i++) {
    window.scrollBy(0, 800);
    await new Promise((r) => setTimeout(r, 500));
  }
  const out = [];
  for (const b of document.querySelectorAll("div[data-hook='review']")) {
    const rEl = b.querySelector("i[data-hook*='review-star-rating'] span");
    const tEl = b.querySelector("a[data-hook='review-title'], span[data-hook='review-title']");
    const bodyEl = b.querySelector("span[data-hook='review-body']");
    const dateEl = b.querySelector("span[data-hook='review-date']");
    out.push({
      review_id: b.id || `amz_${out.length}`,
      rating: getRating(rEl),
      title: tEl ? tEl.textContent.trim() : null,
      body: bodyEl ? bodyEl.textContent.trim() : "",
      date: dateEl ? dateEl.textContent.trim() : null,
      verified_purchase: !!b.querySelector("span[data-hook='avp-badge']"),
    });
  }
  return out;
})();
