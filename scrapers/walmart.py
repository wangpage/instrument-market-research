"""Walmart: Playwright + stealth，从 __NEXT_DATA__ 拿结构化数据
PerimeterX 的 PRESS & HOLD 验证通过自动化按住 + 微动通过"""
import asyncio
import json
import logging
import random
import re
from typing import List
from urllib.parse import urlencode

from config.schema import Product, Review
from scrapers.browser_base import BrowserBaseScraper
from scrapers.base import estimate_sold_from_reviews

log = logging.getLogger(__name__)


async def _solve_press_and_hold(page, duration=10.0):
    """自动完成 PerimeterX PRESS & HOLD 验证"""
    # 找按钮
    btn = None
    box = None
    for sel in ["#px-captcha", "button:has-text('PRESS')", "div[role='button']"]:
        try:
            btn = await page.query_selector(sel)
            if btn:
                box = await btn.bounding_box()
                if box:
                    break
        except Exception:
            pass
    if not btn or not box:
        return False
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2
    # 预移动（带轨迹）
    for _ in range(3):
        await page.mouse.move(
            cx + random.randint(-25, 25),
            cy + random.randint(-25, 25),
            steps=random.randint(5, 10),
        )
        await asyncio.sleep(random.uniform(0.15, 0.35))
    await page.mouse.move(cx, cy, steps=8)
    await asyncio.sleep(0.2)
    await page.mouse.down()
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < duration:
        await page.mouse.move(
            cx + random.uniform(-2, 2), cy + random.uniform(-2, 2), steps=2
        )
        await asyncio.sleep(random.uniform(0.1, 0.3))
    await page.mouse.up()
    await asyncio.sleep(4)
    return "blocked" not in page.url


class WalmartScraper(BrowserBaseScraper):
    platform = "walmart"
    _query_count = 0

    async def _warmup(self):
        """间隔几个 query 访问首页/类目页 reset 反爬怀疑度"""
        page = await self._context.new_page()
        try:
            target = "https://www.walmart.com/cp/musical-instruments/4170"
            await page.goto(target, timeout=30000)
            await self._human_pause(3.0, 5.0)
            await self._human_scroll(page, steps=3)
        except Exception as e:
            log.warning(f"[walmart] warmup: {e}")
        finally:
            await page.close()

    async def search(self, category, subcategory, query, is_smart, top_n) -> List[Product]:
        # 每 3 个 query warmup 一次
        if self._query_count > 0 and self._query_count % 3 == 0:
            log.info(f"[walmart] warmup before query #{self._query_count}")
            await self._warmup()
            await self._human_pause(8.0, 15.0)
        self._query_count += 1

        products = await self._do_search(category, subcategory, query, is_smart, top_n)
        # 失败重试一次（先访问类目页）
        if not products:
            log.info(f"[walmart] {query!r} empty, retry after warmup")
            await self._warmup()
            await self._human_pause(15.0, 25.0)
            products = await self._do_search(category, subcategory, query, is_smart, top_n)
        return products

    async def _do_search(self, category, subcategory, query, is_smart, top_n):
        page = await self._context.new_page()
        url = f"https://www.walmart.com/search?{urlencode({'q': query})}"
        products: List[Product] = []
        try:
            await self._goto_like_human(page, url)
            await self._human_pause(2.0, 4.0)
            # 检测 PerimeterX 拦截，尝试自动 press-hold
            if "blocked" in page.url or "px-captcha" in page.url:
                log.info(f"[walmart] captcha detected on {query!r}, solving press-hold...")
                ok = await _solve_press_and_hold(page, duration=10.0)
                if not ok:
                    log.warning(f"[walmart] press-hold failed, retry 15s...")
                    ok = await _solve_press_and_hold(page, duration=15.0)
                if not ok:
                    log.warning(f"[walmart] still blocked: {page.url}")
                    return []
                log.info(f"[walmart] captcha solved ✓")
                await self._human_pause(2.0, 3.5)
            next_data = await page.evaluate(
                "() => { const el = document.getElementById('__NEXT_DATA__'); return el && el.textContent; }"
            )
            if next_data:
                try:
                    data = json.loads(next_data)
                    products = self._parse_next(data, category, subcategory, query, is_smart, top_n)
                except Exception as e:
                    log.warning(f"[walmart] next_data parse: {e}")
            if not products:
                html = await page.content()
                products = self._parse_html(html, category, subcategory, query, is_smart, top_n)
        except Exception as e:
            log.warning(f"[walmart] {query!r}: {e}")
        finally:
            await page.close()
        self._save_raw("search", query, [p.model_dump() for p in products])
        return products

    def _dig(self, obj, path_keys):
        for k in path_keys:
            if isinstance(obj, dict) and k in obj:
                obj = obj[k]
            else:
                return None
        return obj

    def _parse_next(self, data, category, subcategory, query, is_smart, top_n):
        items = []
        # 已确认路径: pageProps.initialData.searchResult.itemStacks[0].items
        candidates = [
            ["props", "pageProps", "initialData", "searchResult", "itemStacks", 0, "items"],
            ["props", "pageProps", "initialData", "searchResult", "itemStacks", 0, "itemsV2"],
            ["props", "pageProps", "initialData", "data", "search", "itemStacks", 0, "items"],
        ]
        for path in candidates:
            cur = data
            ok = True
            for k in path:
                if isinstance(cur, list) and isinstance(k, int) and k < len(cur):
                    cur = cur[k]
                elif isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    ok = False
                    break
            if ok and isinstance(cur, list) and cur:
                items = cur
                break

        products = []
        for idx, it in enumerate(items[:top_n * 3]):  # 多抓点，过滤 ad 之后还够 top_n
            if not isinstance(it, dict):
                continue
            sku = it.get("usItemId") or it.get("id") or it.get("itemId")
            if not sku:
                continue
            title = it.get("name") or it.get("title") or ""
            if not title:
                continue
            url = it.get("canonicalUrl") or it.get("productPageUrl") or ""
            if url and not url.startswith("http"):
                url = f"https://www.walmart.com{url}"
            price_info = it.get("priceInfo") or {}
            price_str = price_info.get("linePrice") or price_info.get("itemPrice") or ""
            price_usd = None
            if price_str:
                pm = re.search(r"([\d,]+\.\d+|[\d,]+)", price_str.replace("$", ""))
                if pm:
                    try:
                        price_usd = float(pm.group(1).replace(",", ""))
                    except ValueError:
                        pass
            was_str = price_info.get("wasPrice") or ""
            orig = None
            if was_str and isinstance(was_str, str):
                wm = re.search(r"([\d,]+\.\d+|[\d,]+)", was_str.replace("$", ""))
                if wm:
                    try:
                        orig = float(wm.group(1).replace(",", ""))
                    except ValueError:
                        pass
            rating = it.get("averageRating")
            try:
                rating = float(rating) if rating is not None else None
            except (TypeError, ValueError):
                rating = None
            review_count = it.get("numberOfReviews")
            try:
                review_count = int(review_count) if review_count is not None else None
            except (TypeError, ValueError):
                review_count = None

            img = (it.get("imageInfo") or {}).get("thumbnailUrl") or it.get("imageUrl")
            brand = it.get("brand") or ((it.get("seller") or {}).get("name") if isinstance(it.get("seller"), dict) else None)
            seller_name = (it.get("seller") or {}).get("name") if isinstance(it.get("seller"), dict) else None

            products.append(Product(
                platform=self.platform,
                query_keyword=query,
                category=category,
                subcategory=subcategory,
                rank_in_search=len(products) + 1,
                title=title,
                brand=brand,
                asin_or_sku=str(sku),
                url=url,
                image_url=img,
                price_usd=price_usd,
                original_price_usd=orig,
                currency_raw="USD",
                rating=rating,
                review_count=review_count,
                sold_count_estimated=estimate_sold_from_reviews(review_count),
                seller_name=seller_name,
                is_smart_instrument=is_smart,
            ))
            if len(products) >= top_n:
                break
        return products

    def _parse_html(self, html, category, subcategory, query, is_smart, top_n):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('div[data-item-id], [link-identifier]')
        products = []
        for card in cards:
            if len(products) >= top_n:
                break
            sku = card.get("data-item-id") or card.get("link-identifier")
            if not sku:
                continue
            title_el = card.select_one("span.w_q67L, span[data-automation-id='product-title']")
            if not title_el:
                continue
            price_el = card.select_one("div[data-automation-id='product-price'] span")
            price_text = price_el.get_text(strip=True) if price_el else None
            price_usd = None
            if price_text:
                m = re.search(r"\$?([\d,.]+)", price_text)
                if m:
                    try:
                        price_usd = float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass
            link_el = card.select_one("a[link-identifier]") or card.select_one("a")
            href = link_el.get("href", "") if link_el else ""
            url = f"https://www.walmart.com{href}" if href.startswith("/") else href
            products.append(Product(
                platform=self.platform,
                query_keyword=query,
                category=category,
                subcategory=subcategory,
                rank_in_search=len(products) + 1,
                title=title_el.get_text(strip=True),
                asin_or_sku=str(sku),
                url=url,
                price_usd=price_usd,
                currency_raw="USD",
                price_raw=price_text,
                is_smart_instrument=is_smart,
            ))
        return products

    async def fetch_reviews(self, sku, top_n) -> List[Review]:
        page = await self._context.new_page()
        url = f"https://www.walmart.com/reviews/product/{sku}"
        reviews: List[Review] = []
        try:
            await self._goto_like_human(page, url)
            if await self._is_blocked(page):
                return []
            # Walmart 评论通常要再滚动 / 翻页
            await self._human_scroll(page, steps=4)
            next_data = await page.evaluate(
                "() => { const el = document.getElementById('__NEXT_DATA__'); return el && el.textContent; }"
            )
            if next_data:
                try:
                    data = json.loads(next_data)
                    reviews = self._parse_reviews(data, sku, top_n)
                except Exception as e:
                    log.warning(f"[walmart] reviews parse: {e}")
        except Exception as e:
            log.warning(f"[walmart] reviews page {sku}: {e}")
        finally:
            await page.close()
        self._save_raw("reviews", sku, [r.model_dump() for r in reviews])
        return reviews

    def _parse_reviews(self, data, sku, top_n):
        # 尝试多路径
        review_list = None
        candidates = [
            ["props", "pageProps", "initialData", "data", "reviews", "customerReviews"],
            ["props", "pageProps", "initialData", "reviews", "customerReviews"],
            ["props", "pageProps", "initialData", "data", "reviews"],
        ]
        for path in candidates:
            cur = data
            ok = True
            for k in path:
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    ok = False
                    break
            if ok and isinstance(cur, list):
                review_list = cur
                break
            if ok and isinstance(cur, dict) and "customerReviews" in cur:
                review_list = cur["customerReviews"]
                break

        if not review_list:
            return []
        out = []
        for idx, rv in enumerate(review_list[:top_n]):
            if not isinstance(rv, dict):
                continue
            out.append(Review(
                platform="walmart",
                asin_or_sku=sku,
                review_id=str(rv.get("reviewId") or rv.get("id") or f"wm_{idx}"),
                author=rv.get("userNickname") or ((rv.get("reviewer") or {}).get("nickname") if isinstance(rv.get("reviewer"), dict) else None),
                rating=rv.get("rating"),
                date=rv.get("submissionTime") or rv.get("reviewSubmissionTime"),
                title=rv.get("reviewTitle"),
                body=rv.get("reviewText") or "",
                helpful_count=rv.get("positiveFeedback"),
            ))
        return out
