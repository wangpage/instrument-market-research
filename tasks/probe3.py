import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.async_api import async_playwright


async def probe(p, url, label, wait=5):
    print(f"\n>>> {label}: {url[:90]}")
    try:
        await p.goto(url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(wait)
        html = await p.content()
        cur = p.url
        title = await p.title()
        is_block = any(k in cur.lower() for k in ("blocked","captcha","challenge","verify"))
        is_login = "login" in cur.lower()
        flag = "🚫BLOCK" if is_block else ("🔒LOGIN" if is_login else "✅OK")
        print(f"  {flag}  size={len(html)}  title={title[:40]}")
        print(f"  → {cur[:100]}")
        return {"label": label, "ok": (not is_block and not is_login), "url": cur, "size": len(html)}
    except Exception as e:
        print(f"  ❌ ERR: {str(e)[:120]}")
        return {"label": label, "ok": False, "err": str(e)[:120]}


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    p = await ctx.new_page()

    print("=== Walmart 探测 ===")
    await probe(p, "https://www.walmart.com/", "主页")
    await asyncio.sleep(3)
    await probe(p, "https://www.walmart.com/search?q=smart+guitar", "search 直链")
    await asyncio.sleep(3)
    # 内部跳转：从首页找到 search box 输入
    await p.goto("https://www.walmart.com/", timeout=30000)
    await asyncio.sleep(3)
    # 模拟在 search box 输入
    try:
        await p.fill("input[name='q']", "smart guitar", timeout=5000)
        await p.keyboard.press("Enter")
        await asyncio.sleep(5)
        cur = p.url
        title = await p.title()
        print(f"  search-box flow: {cur[:100]}  title={title[:40]}")
    except Exception as e:
        print(f"  search-box flow ERR: {e}")

    print("\n=== Temu 探测 ===")
    await asyncio.sleep(5)
    await probe(p, "https://www.temu.com/", "主页", wait=6)
    await asyncio.sleep(8)
    await probe(p, "https://www.temu.com/search_result.html?search_key=smart+guitar", "search 直链", wait=8)

    print("\n=== TikTok Shop 探测 ===")
    await asyncio.sleep(5)
    await probe(p, "https://www.tiktok.com/", "TikTok 主页")
    await asyncio.sleep(3)
    await probe(p, "https://www.tiktok.com/shop/", "shop tab")
    await asyncio.sleep(3)
    await probe(p, "https://www.tiktok.com/shop/s/guitar", "shop search")
    await asyncio.sleep(3)
    await probe(p, "https://shop.tiktok.com/view/search?q=guitar", "shop subdomain search")

    await p.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
