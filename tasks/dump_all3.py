"""dump 3 平台 search 页结构，找到正确 selector"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.async_api import async_playwright


async def dump(p, url, name, scroll=4, wait=8):
    print(f"\n>>> {name}")
    await p.goto(url, timeout=45000)
    await asyncio.sleep(wait)
    for _ in range(scroll):
        await p.mouse.wheel(0, 800)
        await asyncio.sleep(1)
    html = await p.content()
    Path(f"/tmp/{name}_dump.html").write_text(html, encoding="utf-8")
    print(f"  size={len(html)}")
    print(f"  title={(await p.title())[:50]}")
    return html


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    p = await ctx.new_page()

    # Walmart
    html = await dump(p, "https://www.walmart.com/search?q=smart+guitar", "walmart")
    # 找商品标志
    import re
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    print(f"  __NEXT_DATA__ size: {len(nd.group(1)) if nd else 0}")
    items_count = len(re.findall(r'"usItemId"\s*:\s*"?(\d+)"?', html))
    print(f"  usItemId 数: {items_count}")
    sample_ids = re.findall(r'"usItemId"\s*:\s*"?(\d+)"?', html)[:5]
    print(f"  sample IDs: {sample_ids}")

    await asyncio.sleep(3)
    # TikTok Shop
    html = await dump(p, "https://www.tiktok.com/shop/s/smart%20guitar", "tiktok", wait=15, scroll=8)
    pdp_links = re.findall(r'/shop/pdp/[^"\s]+/(\d+)', html)
    print(f"  TT pdp 链接数: {len(pdp_links)}")
    print(f"  unique: {len(set(pdp_links))}")
    if pdp_links:
        print(f"  sample: {pdp_links[:5]}")

    await asyncio.sleep(3)
    # Temu
    html = await dump(p, "https://www.temu.com/search_result.html?search_key=smart+guitar", "temu", wait=10, scroll=6)
    g_ids = re.findall(r'-g-(\d+)\.html', html)
    print(f"  Temu goods_id 数: {len(set(g_ids))}")

    await p.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
