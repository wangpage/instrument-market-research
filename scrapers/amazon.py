import asyncio
import logging
import re
from typing import List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from config.schema import Product, Review
from scrapers.base import BaseScraper, BlockedError, parse_price, parse_int, estimate_sold_from_reviews

log = logging.getLogger(__name__)

BASE = "https://www.amazon.com"

# 强制美区定价 & 英文 UI
# i18n-prefs=USD 强制 USD 货币
# lc-main=en_US 强制英文
# sp-cdn="L5Z9:US" CDN 地区
US_COOKIES = {
    "i18n-prefs": "USD",
    "lc-main": "en_US",
    "sp-cdn": '"L5Z9:US"',
}


class AmazonScraper(BaseScraper):
    platform = "amazon"

    async def __aenter__(self):
        await super().__aenter__()
        # 注入美区 cookie
        for k, v in US_COOKIES.items():
            self._client.cookies.set(k, v, domain=".amazon.com")
        # 访问首页让服务端下发额外的 session cookie
        try:
            await self._get(f"{BASE}/?language=en_US&currency=USD")
        except Exception as e:
            log.warning(f"[amazon] init visit failed: {e}")
        return self

    async def search(self, category, subcategory, query, is_smart, top_n):
        products: List[Product] = []
        page = 1
        while len(products) < top_n and page <= 5:
            url = f"{BASE}/s?{urlencode({'k': query, 'page': page})}"
            try:
                r = await self._get(url)
            except BlockedError as e:
                log.warning(f"[amazon] blocked on page {page}: {e}")
                break
            items = self._parse_search(r.text, query)
            if not items:
                break
            for idx, raw in enumerate(items):
                rank = (page - 1) * len(items) + idx + 1
                p = self._to_product(raw, category, subcategory, query, is_smart, rank)
                if p:
                    products.append(p)
                if len(products) >= top_n:
                    break
            page += 1
        self.save_raw("search", query, [p.model_dump() for p in products])
        return products

    def _parse_search(self, html: str, query: str) -> List[dict]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('div.s-result-item[data-asin]')
        out = []
        for card in cards:
            asin = card.get("data-asin", "").strip()
            if not asin or len(asin) < 10:
                continue
            title_el = card.select_one("h2 span")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            link_el = card.select_one("h2 a")
            href = link_el.get("href") if link_el else None
            url = urljoin(BASE, href) if href else f"{BASE}/dp/{asin}"

            price_whole = card.select_one("span.a-price span.a-offscreen")
            price_text = price_whole.get_text(strip=True) if price_whole else None

            # Amazon A/B 测试两种布局:
            # (A) 单个组合 aria-label: "Rated 4.3 out of 5 stars by 266 reviews"
            # (B) 分开两个 aria-label: "4.5 out of 5 stars, rating details" + "162 ratings"
            rating = None
            review_count_text = None
            for el in card.find_all(attrs={"aria-label": True}):
                lbl = el.get("aria-label", "")
                if "out of 5 stars by" in lbl:
                    m = re.search(r"Rated\s+([\d.]+)\s+out of 5 stars by\s+([\d,]+)", lbl)
                    if m:
                        rating = float(m.group(1))
                        review_count_text = m.group(2)
                        break
                if rating is None and "out of 5 stars" in lbl:
                    m = re.search(r"([\d.]+)\s+out of 5 stars", lbl)
                    if m:
                        rating = float(m.group(1))
                if review_count_text is None and re.match(r"^[\d,]+\s+ratings?$", lbl.strip()):
                    review_count_text = lbl.strip()
            if rating is None:
                rating_el = card.select_one("span.a-icon-alt")
                if rating_el:
                    m = re.search(r"([\d.]+)\s*out of", rating_el.get_text(strip=True))
                    if m:
                        rating = float(m.group(1))

            img_el = card.select_one("img.s-image")
            image_url = img_el.get("src") if img_el else None

            brand_el = card.select_one("h2 + div span.a-size-base-plus, span.a-size-base-plus")
            brand = brand_el.get_text(strip=True) if brand_el else None

            out.append({
                "asin": asin,
                "title": title,
                "url": url,
                "price_raw": price_text,
                "rating": rating,
                "review_count_text": review_count_text,
                "image_url": image_url,
                "brand": brand,
            })
        return out

    def _to_product(self, raw, category, subcategory, query, is_smart, rank) -> Optional[Product]:
        price_usd, price_raw = parse_price(raw.get("price_raw") or "")
        review_count = parse_int(raw.get("review_count_text") or "")
        return Product(
            platform=self.platform,
            query_keyword=query,
            category=category,
            subcategory=subcategory,
            rank_in_search=rank,
            title=raw["title"],
            brand=raw.get("brand"),
            asin_or_sku=raw["asin"],
            url=raw["url"],
            image_url=raw.get("image_url"),
            price_usd=price_usd,
            currency_raw="USD",
            price_raw=price_raw,
            rating=raw.get("rating"),
            review_count=review_count,
            sold_count_estimated=estimate_sold_from_reviews(review_count),
            is_smart_instrument=is_smart,
        )

    async def enrich_detail(self, product: Product) -> Product:
        """抓详情页拿 BSR 和精确品牌"""
        try:
            r = await self._get(product.url)
        except BlockedError as e:
            log.warning(f"[amazon] detail blocked: {e}")
            return product
        soup = BeautifulSoup(r.text, "lxml")

        if not product.brand:
            brand_el = soup.select_one("#bylineInfo")
            if brand_el:
                txt = brand_el.get_text(strip=True)
                m = re.search(r"(?:Brand:|by)\s*(.+)", txt)
                product.brand = (m.group(1) if m else txt).strip()

        for row in soup.select("#productDetails_detailBullets_sections1 tr, #detailBullets_feature_div li, #productDetails_techSpec_section_1 tr"):
            txt = row.get_text(" ", strip=True)
            if "Best Sellers Rank" in txt or "Amazon Best Sellers Rank" in txt:
                m = re.search(r"#([\d,]+)\s+in\s+([^(\n#]+)", txt)
                if m:
                    product.bsr_rank = int(m.group(1).replace(",", ""))
                    product.bsr_category = m.group(2).strip()
                break

        date_el = soup.find(string=re.compile(r"Date First Available"))
        if date_el:
            parent = date_el.parent
            sib = parent.find_next("span") if parent else None
            if sib:
                product.listing_date = sib.get_text(strip=True)

        return product

    async def fetch_reviews(self, sku: str, top_n: int) -> List[Review]:
        reviews: List[Review] = []
        page = 1
        while len(reviews) < top_n and page <= 3:
            url = f"{BASE}/product-reviews/{sku}/?pageNumber={page}&sortBy=helpful"
            try:
                r = await self._get(url)
            except BlockedError as e:
                log.warning(f"[amazon] reviews blocked: {e}")
                break
            batch = self._parse_reviews(r.text, sku)
            if not batch:
                break
            reviews.extend(batch)
            page += 1
        self.save_raw("reviews", sku, [rv.model_dump() for rv in reviews[:top_n]])
        return reviews[:top_n]

    def _parse_reviews(self, html: str, sku: str) -> List[Review]:
        soup = BeautifulSoup(html, "lxml")
        out = []
        for block in soup.select("div[data-hook='review']"):
            rid = block.get("id", "")
            rating_el = block.select_one("i[data-hook='review-star-rating'] span, i[data-hook='cmps-review-star-rating'] span")
            rating = None
            if rating_el:
                m = re.search(r"([\d.]+)", rating_el.get_text())
                if m:
                    rating = float(m.group(1))
            title_el = block.select_one("a[data-hook='review-title'], span[data-hook='review-title']")
            title = title_el.get_text(" ", strip=True) if title_el else None
            body_el = block.select_one("span[data-hook='review-body']")
            body = body_el.get_text(" ", strip=True) if body_el else ""
            date_el = block.select_one("span[data-hook='review-date']")
            date = date_el.get_text(strip=True) if date_el else None
            author_el = block.select_one("span.a-profile-name")
            author = author_el.get_text(strip=True) if author_el else None
            verified_el = block.select_one("span[data-hook='avp-badge']")
            helpful_el = block.select_one("span[data-hook='helpful-vote-statement']")
            helpful = parse_int(helpful_el.get_text()) if helpful_el else None
            out.append(Review(
                platform="amazon",
                asin_or_sku=sku,
                review_id=rid or f"{sku}_{len(out)}",
                author=author,
                rating=rating,
                date=date,
                title=title,
                body=body,
                helpful_count=helpful,
                verified_purchase=bool(verified_el),
            ))
        return out
