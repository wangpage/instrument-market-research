# 乐器市场调研 Chrome 扩展

绕开反爬——**读已渲染 DOM** 而不是发请求。

## 安装

1. 打开 Chrome：`chrome://extensions/`
2. 右上角开启「开发者模式」
3. 点「加载已解压的扩展程序」
4. 选择 `/Users/page/Desktop/爬虫/extension/` 目录
5. 扩展图标出现在工具栏（蓝色方块）

## 使用

**方式 A：批量模式（推荐）**
1. 点击扩展图标打开 popup
2. 勾选要抓的平台
3. 编辑关键词（每行格式 `关键词|大类|子品类|is_smart`）
4. 点「开始批量抓取」
5. 扩展会自动在当前 tab 依次打开每个 search URL，content script 抽取 DOM 数据发回
6. 全程看得见，Temu/TikTok 如弹 captcha 手动过一次就继续跑
7. 完成后点「导出 CSV」保存

**方式 B：手动模式**
1. 你正常浏览目标网站的 search 页
2. 页面加载后，点击扩展的「🎯 只抓当前页」
3. 数据累积到扩展本地存储

## 支持的平台

- Amazon (`/s?k=...`)
- eBay (`/sch/i.html?_nkw=...`)
- Walmart (`/search?q=...`)
- Temu (`/search_result.html?search_key=...`)
- TikTok Shop (`/shop/s/...`) — 需要美区账号

## 数据字段

CSV 包含：platform, query_keyword, category, subcategory, rank_in_search, title, brand, asin_or_sku, url, image_url, price_usd, original_price_usd, currency_raw, price_raw, rating, review_count, sold_count_text, sold_count_estimated, seller_name, seller_country, is_smart_instrument, scraped_at

## 合并到 master

扩展导出的 CSV 与 Python 爬虫的 Excel 字段完全兼容。把 CSV 转 Excel 后放 `data/processed/products_<platform>.xlsx` 再跑 `python3 tasks/build_report.py` 自动合并。
