"""验证 CDP 连接 + 抓美区 eBay"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["BROWSER_MODE"] = "cdp"

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from scrapers.ebay import EbayScraper


async def main():
    print("=== CDP 连接测试 ===")
    print("确认你的 Chrome 已用 --remote-debugging-port=9222 启动并挂了美国 VPN\n")

    async with EbayScraper() as s:
        print(f"Connected. Browser: {s._browser.browser_type.name}")
        print(f"Contexts: {len(s._browser.contexts)}")

        # 先验证 IP / 地区：访问 ipinfo
        page = await s._context.new_page()
        try:
            await page.goto("https://ipinfo.io/json", timeout=15000)
            body = await page.content()
            import re
            m = re.search(r'"country"\s*:\s*"([^"]+)"', body)
            region = re.search(r'"region"\s*:\s*"([^"]+)"', body)
            city = re.search(r'"city"\s*:\s*"([^"]+)"', body)
            print(f"当前 IP 地区: country={m.group(1) if m else '?'}, region={region.group(1) if region else '?'}, city={city.group(1) if city else '?'}")
            if m and m.group(1) != "US":
                print(f"⚠️  IP 不在美国 ({m.group(1)}) — eBay 可能仍返回本地化数据")
        except Exception as e:
            print(f"IP 检测失败: {e}")
        finally:
            await page.close()

        # 测 eBay 抓取
        print("\n--- 测试 eBay smart guitar Top 8 ---")
        ps = await s.search("smart", "smart_guitar", "smart guitar", True, 8)
        print(f"got {len(ps)} products:")
        for p in ps:
            is_english = all(ord(c) < 128 for c in (p.title or "")[:30])
            print(f"  ${p.price_usd:>8}  [{'EN' if is_english else 'CN'}]  {p.title[:80]}  id={p.asin_or_sku}")


if __name__ == "__main__":
    asyncio.run(main())
