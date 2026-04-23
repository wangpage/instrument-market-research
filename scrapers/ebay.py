"""eBay: 优先走 Playwright 浏览器模式（反爬最近收紧，httpx 直连基本被 splash 拦截）"""
import logging
import re
from typing import List
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from config.schema import Product, Review
from scrapers.browser_base import BrowserBaseScraper
from scrapers.base import parse_price, parse_int

log = logging.getLogger(__name__)


class EbayScraper(BrowserBaseScraper):
    platform = "ebay"

    async def __aenter__(self):
        await super().__aenter__()
        # 强制美区英文 UI
        try:
            await self._context.add_cookies([
                {"name": "dp1", "value": "bpbf/%231e6000000048#pbf/%231e60000000006edd22", "domain": ".ebay.com", "path": "/"},
                {"name": "ebay", "value": "%5Ecv%3D130%5Esbf%3D%23000000%5E", "domain": ".ebay.com", "path": "/"},
                {"name": "gh_fc_language", "value": "en", "domain": ".ebay.com", "path": "/"},
            ])
        except Exception as e:
            log.warning(f"[ebay] cookie set: {e}")
        # 首次访问 ebay.com 让其下发 session cookie
        page = await self._context.new_page()
        try:
            await page.goto("https://www.ebay.com/?_trksid=p_cld_guid", timeout=30000)
            await self._human_pause(1.5, 3.0)
        except Exception:
            pass
        finally:
            await page.close()
        return self

    async def search(self, category, subcategory, query, is_smart, top_n) -> List[Product]:
        page = await self._context.new_page()
        url = f"https://www.ebay.com/sch/i.html?{urlencode({'_nkw': query, 'LH_BIN': 1, 'LH_PrefLoc': 1})}"
        products: List[Product] = []
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                log.warning(f"[ebay] blocked on {query!r}")
                return []
            html = await page.content()
            products = self._parse(html, category, subcategory, query, is_smart, top_n)
        except Exception as e:
            log.warning(f"[ebay] error {query!r}: {e}")
        finally:
            await page.close()
        self._save_raw("search", query, [p.model_dump() for p in products])
        return products

    def _parse(self, html, category, subcategory, query, is_smart, top_n):
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(".s-card, li.s-item")
        products = []
        for card in cards:
            if len(products) >= top_n:
                break
            # 优先拿 data-listingid，否则从 href 里抠
            item_id = card.get("data-listingid")
            href = None
            link_el = card.select_one("a.s-card__link, a.s-item__link")
            if link_el:
                href = link_el.get("href")
            if not item_id and href:
                m = re.search(r"/itm/(\d{10,})", href)
                item_id = m.group(1) if m else None
            if not item_id:
                continue
            if item_id == "123456":
                continue  # eBay 广告占位

            # title: 优先 img.alt，次之 s-card__title
            title = None
            img_el = card.select_one("img.s-card__image, .s-item__image img, img")
            if img_el and img_el.get("alt"):
                title = img_el["alt"].strip()
            if not title:
                title_el = card.select_one(".s-card__title, .s-item__title, [class*='title']")
                if title_el:
                    title = title_el.get_text(" ", strip=True)
            if not title or "Shop on eBay" in title:
                continue

            price_el = card.select_one(".s-card__price, .s-item__price, [class*='price']")
            price_text = price_el.get_text(strip=True) if price_el else None
            price_usd, price_raw = parse_price(price_text) if price_text else (None, None)

            # sold count: 新版可能在 .su-styled-text 或 data-testid
            sold_el = card.find(string=re.compile(r"sold|Sold|已售"))
            sold_text = str(sold_el).strip() if sold_el else None

            # 卖家位置：新版有 .s-card__location
            loc_el = card.select_one(".s-card__location, .s-item__location, .s-item__itemLocation")
            loc_text = loc_el.get_text(strip=True) if loc_el else None

            image_url = img_el.get("src") or img_el.get("data-src") if img_el else None

            products.append(Product(
                platform=self.platform,
                query_keyword=query,
                category=category,
                subcategory=subcategory,
                rank_in_search=len(products) + 1,
                title=title,
                asin_or_sku=str(item_id),
                url=href.split("?")[0] if href else f"https://www.ebay.com/itm/{item_id}",
                image_url=image_url,
                price_usd=price_usd,
                currency_raw="USD",
                price_raw=price_raw,
                sold_count_text=sold_text,
                sold_count_estimated=parse_int(sold_text) if sold_text else None,
                seller_country=loc_text,
                is_smart_instrument=is_smart,
            ))
        return products

    async def fetch_reviews(self, sku, top_n) -> List[Review]:
        """eBay item-level reviews are rare; try /itm/{id} -> reviews tab"""
        page = await self._context.new_page()
        reviews = []
        url = f"https://www.ebay.com/itm/{sku}"
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                return []
            # eBay 商品评论不常见，有就抓
            review_blocks = await page.query_selector_all("[data-testid='x-review-details'] article, .rvw-rating article")
            for idx, rb in enumerate(review_blocks[:top_n]):
                text = await rb.inner_text()
                if not text:
                    continue
                reviews.append(Review(
                    platform="ebay",
                    asin_or_sku=sku,
                    review_id=f"{sku}_{idx}",
                    body=text[:1000],
                ))
        except Exception as e:
            log.warning(f"[ebay] review error {sku}: {e}")
        finally:
            await page.close()
        self._save_raw("reviews", sku, [r.model_dump() for r in reviews])
        return reviews
