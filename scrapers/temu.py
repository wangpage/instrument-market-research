"""Temu: Playwright + stealth，评论和"已售"在商品卡和详情页"""
import json
import logging
import re
from typing import List
from urllib.parse import urlencode, unquote

from bs4 import BeautifulSoup

from config.schema import Product, Review
from scrapers.browser_base import BrowserBaseScraper

log = logging.getLogger(__name__)


class TemuScraper(BrowserBaseScraper):
    platform = "temu"

    _warmed_up = False

    async def search(self, category, subcategory, query, is_smart, top_n) -> List[Product]:
        """Temu: 完全模拟真实用户 — 进主页、点击 search box、键盘打字、按 Enter"""
        page = await self._context.new_page()
        products: List[Product] = []
        try:
            # 每次都从首页进入，最真实的导航
            await page.goto("https://www.temu.com/", timeout=30000)
            await self._human_pause(3.0, 5.0)
            await self._human_mousemove(page)

            # 找 search box
            search_box = None
            for sel in [
                'input[placeholder*="Search" i]',
                'input[name="search"]',
                'input[type="search"]',
                'input[class*="searchInput" i]',
                'input[class*="search" i]',
            ]:
                try:
                    search_box = await page.wait_for_selector(sel, timeout=3000)
                    if search_box:
                        break
                except Exception:
                    continue

            if search_box:
                # 点击 + 清空 + 打字 + Enter（完全真实流程）
                await search_box.click()
                await self._human_pause(0.4, 0.9)
                await search_box.press("Control+A")
                await search_box.press("Delete")
                # 逐字符输入带微小延迟（人类打字节奏）
                import random
                for ch in query:
                    await search_box.type(ch, delay=random.randint(50, 150))
                await self._human_pause(0.3, 0.8)
                await search_box.press("Enter")
                # 等待导航
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception:
                    pass
                await self._human_pause(3.0, 5.0)
            else:
                # 兜底：直接 URL（search_method=user 模拟）
                from urllib.parse import quote
                await page.goto(
                    f"https://www.temu.com/search_result.html?search_key={quote(query, safe='')}&search_method=user",
                    timeout=30000,
                )
                await self._human_pause(4.0, 6.0)

            await self._human_scroll(page, steps=5)
            await self._human_pause(1.5, 3.0)
            html = await page.content()
            products = self._parse_html(html, category, subcategory, query, is_smart, top_n)
            if not products:
                log.info(f"[temu] empty on {query!r}, scroll more and retry")
                await self._human_scroll(page, steps=4)
                await self._human_pause(2.0, 4.0)
                html = await page.content()
                products = self._parse_html(html, category, subcategory, query, is_smart, top_n)
        except Exception as e:
            log.warning(f"[temu] {query!r}: {e}")
        finally:
            await page.close()
        self._save_raw("search", query, [p.model_dump() for p in products])
        return products

    def _parse_html(self, html, category, subcategory, query, is_smart, top_n):
        soup = BeautifulSoup(html, "lxml")
        seen = set()
        products = []
        # Temu URL: /us-{lang}/{slug}-g-{goods_id}.html
        for a in soup.select("a[href]"):
            if len(products) >= top_n:
                break
            href = a.get("href", "")
            m = re.search(r"-g-(\d+)\.html", href)
            if not m:
                continue
            gid = m.group(1)
            if gid in seen:
                continue
            seen.add(gid)
            # title: img alt 最可靠
            img = a.select_one("img")
            title = (img.get("alt", "").strip() if img else "") or ""
            if title in ("image", "img", ""):
                # slug 里反推 title 片段
                slug_m = re.search(r"/([^/]+)-g-\d+\.html", href)
                title = unquote(slug_m.group(1).replace("-", " ")) if slug_m else ""
                title = title[:150]
            img_src = img.get("src") or img.get("data-src") if img else None
            # price & sold: 往父层找 $xxx / sold
            container = a
            for _ in range(4):
                container = container.parent
                if not container:
                    break
                txt = container.get_text(" ", strip=True)
                if "$" in txt:
                    break
            price_text = container.get_text(" ", strip=True) if container else ""
            pm = re.search(r"\$\s*([\d,.]+)", price_text)
            price_usd = None
            price_raw = None
            if pm:
                price_raw = f"${pm.group(1)}"
                try:
                    price_usd = float(pm.group(1).replace(",", ""))
                except ValueError:
                    pass
            sold_m = re.search(r"([\d,\.]+[Kk]?\+?)\s*sold", price_text, re.I)
            sold_text = sold_m.group(0) if sold_m else None
            url = f"https://www.temu.com{href}" if href.startswith("/") else href
            products.append(Product(
                platform=self.platform,
                query_keyword=query,
                category=category,
                subcategory=subcategory,
                rank_in_search=len(products) + 1,
                title=title[:300],
                asin_or_sku=str(gid),
                url=url,
                image_url=img_src,
                price_usd=price_usd,
                currency_raw="USD",
                price_raw=price_raw,
                sold_count_text=sold_text,
                is_smart_instrument=is_smart,
            ))
        return products

    async def fetch_reviews(self, sku, top_n) -> List[Review]:
        page = await self._context.new_page()
        reviews = []
        # Temu 详情页 URL 有变种，先试一种
        url = f"https://www.temu.com/goods.html?goods_id={sku}"
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                return []
            await self._human_scroll(page, steps=6)
            cards = await page.query_selector_all("[class*='comment'], [class*='review'], [data-testid*='review']")
            for idx, c in enumerate(cards[:top_n]):
                text = await c.inner_text()
                if not text or len(text) < 5:
                    continue
                reviews.append(Review(
                    platform="temu",
                    asin_or_sku=sku,
                    review_id=f"{sku}_{idx}",
                    body=text[:1000],
                ))
        except Exception as e:
            log.warning(f"[temu] reviews {sku}: {e}")
        finally:
            await page.close()
        self._save_raw("reviews", sku, [r.model_dump() for r in reviews])
        return reviews
