// Popup UI 控制

async function refreshStats() {
  const r = await chrome.runtime.sendMessage({ type: "GET_STATE" });
  document.getElementById("count").textContent = (r.products || []).length;
  document.getElementById("queue").textContent = (r.queue || []).length;
  // 按 platform 分组统计
  const stats = {};
  for (const p of r.products || []) {
    stats[p.platform] = (stats[p.platform] || 0) + 1;
  }
  document.getElementById("platform_stats").innerHTML = Object.entries(stats)
    .map(([p, n]) => `<span class="tag">${p}: ${n}</span>`)
    .join("");
}

document.addEventListener("DOMContentLoaded", () => {
  refreshStats();
  setInterval(refreshStats, 2000);

  document.getElementById("start").addEventListener("click", async () => {
    const platforms = Array.from(document.querySelectorAll(".platform:checked"))
      .map((cb) => cb.value);
    const rawLines = document.getElementById("keywords").value
      .split("\n").map((s) => s.trim()).filter(Boolean);

    const tasks = [];
    for (const line of rawLines) {
      const [query, category, subcategory, isSmart] = line.split("|").map((s) => (s || "").trim());
      if (!query) continue;
      for (const platform of platforms) {
        tasks.push({
          platform, query,
          category: category || "unknown",
          subcategory: subcategory || "unknown",
          is_smart: (isSmart === "true"),
        });
      }
    }
    if (!tasks.length) return alert("没有任务");
    const ok = confirm(`将执行 ${tasks.length} 个查询（${platforms.length} 平台 × ${rawLines.length} 关键词）。每个 ~10-30s。\n是否开始？`);
    if (!ok) return;
    await chrome.runtime.sendMessage({ type: "START_BATCH", tasks });
    refreshStats();
  });

  document.getElementById("scrape_current").addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return alert("找不到当前 tab");
    // 让 content script 执行抓取（通过消息）
    try {
      const r = await chrome.tabs.sendMessage(tab.id, { type: "SCRAPE_NOW" });
      alert(`抓到 ${r?.count || 0} 个商品`);
    } catch (e) {
      alert("当前页不在支持的平台上，或 content script 未加载");
    }
  });

  document.getElementById("export_csv").addEventListener("click", async () => {
    const r = await chrome.runtime.sendMessage({ type: "EXPORT_CSV" });
    if (r.rows === 0) alert("没有数据");
  });

  document.getElementById("export_json").addEventListener("click", async () => {
    const r = await chrome.runtime.sendMessage({ type: "EXPORT_JSON" });
    if (r.rows === 0) alert("没有数据");
  });

  document.getElementById("clear").addEventListener("click", async () => {
    if (!confirm("确定清空所有抓取数据？")) return;
    await chrome.runtime.sendMessage({ type: "CLEAR_DATA" });
    refreshStats();
  });
});
