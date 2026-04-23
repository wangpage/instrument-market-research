"""TikTok Shop: Playwright 直接访问 → 触发 captcha → 降级 Fastmoss 榜单"""
import logging
import re
from typing import List
from urllib.parse import quote

from bs4 import BeautifulSoup

from config.schema import Product, Review
from scrapers.browser_base import BrowserBaseScraper

log = logging.getLogger(__name__)


class TikTokShopScraper(BrowserBaseScraper):
    platform = "tiktok_shop"

    async def search(self, category, subcategory, query, is_smart, top_n) -> List[Product]:
        direct = await self._search_direct(category, subcategory, query, is_smart, top_n)
        if direct:
            return direct
        log.info(f"[tiktok_shop] direct empty, fallback to fastmoss for {query!r}")
        return await self._search_fastmoss(category, subcategory, query, is_smart, top_n)

    async def _search_direct(self, category, subcategory, query, is_smart, top_n):
        page = await self._context.new_page()
        url = f"https://www.tiktok.com/shop/s/{quote(query)}"
        products = []
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                log.warning(f"[tiktok_shop] captcha detected for {query!r}")
                return []
            await self._human_scroll(page, steps=6)
            html = await page.content()
            products = self._parse_shop(html, category, subcategory, query, is_smart, top_n)
        except Exception as e:
            log.warning(f"[tiktok_shop] direct error {query!r}: {e}")
        finally:
            await page.close()
        if products:
            self._save_raw("direct_search", query, [p.model_dump() for p in products])
        return products

    def _parse_shop(self, html, category, subcategory, query, is_smart, top_n):
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("a[data-e2e*='product'], div[data-e2e*='product'], a[href*='/shop/pdp/']")
        products = []
        for card in cards:
            if len(products) >= top_n:
                break
            href = card.get("href") or ""
            m = re.search(r"/product/(\d+)|/pdp/(\d+)|product_id=(\d+)", href)
            if not m:
                continue
            pid = next((g for g in m.groups() if g), None)
            title_el = card.select_one("p, span[data-e2e*='product-title'], div[data-e2e*='title']")
            title = title_el.get_text(" ", strip=True) if title_el else card.get_text(" ", strip=True)[:150]
            price_el = card.find(string=re.compile(r"\$\s*[\d,.]+"))
            price_raw = str(price_el).strip() if price_el else None
            price_usd = None
            if price_raw:
                pm = re.search(r"\$\s*([\d,.]+)", price_raw)
                if pm:
                    try:
                        price_usd = float(pm.group(1).replace(",", ""))
                    except ValueError:
                        pass
            sold_el = card.find(string=re.compile(r"sold", re.I))
            sold_text = str(sold_el).strip() if sold_el else None
            products.append(Product(
                platform=self.platform,
                query_keyword=query,
                category=category,
                subcategory=subcategory,
                rank_in_search=len(products) + 1,
                title=title[:300],
                asin_or_sku=str(pid),
                url=f"https://www.tiktok.com{href}" if href.startswith("/") else href,
                price_usd=price_usd,
                currency_raw="USD",
                price_raw=price_raw,
                sold_count_text=sold_text,
                is_smart_instrument=is_smart,
            ))
        return products

    async def _search_fastmoss(self, category, subcategory, query, is_smart, top_n):
        """Fastmoss 公开榜单 — 用当前浏览器直接访问"""
        page = await self._context.new_page()
        products = []
        url = f"https://www.fastmoss.com/e-commerce/detail?keyword={quote(query)}"
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                return []
            await self._human_scroll(page, steps=3)
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            for idx, row in enumerate(soup.select("tr, .product-row, li[class*='product']")):
                if len(products) >= top_n:
                    break
                text = row.get_text(" ", strip=True)
                if len(text) < 10:
                    continue
                price_m = re.search(r"\$\s*([\d,.]+)", text)
                sold_m = re.search(r"([\d,\.]+[KkMm]?)\s*sold", text, re.I)
                link = row.select_one("a")
                href = link.get("href") if link else None
                products.append(Product(
                    platform=self.platform,
                    query_keyword=query,
                    category=category,
                    subcategory=subcategory,
                    rank_in_search=idx + 1,
                    title=text[:200],
                    asin_or_sku=f"fastmoss_{idx}",
                    url=href or "",
                    price_usd=float(price_m.group(1).replace(",", "")) if price_m else None,
                    price_raw=f"${price_m.group(1)}" if price_m else None,
                    sold_count_text=sold_m.group(0) if sold_m else None,
                    seller_country="TikTok via Fastmoss",
                    is_smart_instrument=is_smart,
                ))
        except Exception as e:
            log.warning(f"[tiktok_shop/fastmoss] {query!r}: {e}")
        finally:
            await page.close()
        self._save_raw("fastmoss_search", query, [p.model_dump() for p in products])
        return products

    async def fetch_reviews(self, sku, top_n) -> List[Review]:
        return []
