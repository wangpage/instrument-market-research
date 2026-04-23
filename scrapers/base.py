import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.platforms import PLATFORMS, common_headers
from config.schema import Product, Review

log = logging.getLogger(__name__)

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


class BlockedError(Exception):
    """页面返回 captcha / 403 / 503 等被封信号"""


class BaseScraper:
    platform: str = ""

    def __init__(self, proxy: Optional[str] = None):
        cfg = PLATFORMS[self.platform]
        self.delay_range = cfg["delay_range"]
        self.max_concurrency = cfg["max_concurrency"]
        self.proxy = proxy or os.getenv("HTTPS_PROXY") or None
        self._sem = asyncio.Semaphore(self.max_concurrency)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            http2=True,
            timeout=30.0,
            follow_redirects=True,
            proxy=self.proxy,
            headers=common_headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client:
            await self._client.aclose()

    async def _sleep(self):
        lo, hi = self.delay_range
        await asyncio.sleep(random.uniform(lo, hi))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((httpx.HTTPError, BlockedError)),
        reraise=True,
    )
    async def _get(self, url, **kwargs):
        async with self._sem:
            await self._sleep()
            headers = kwargs.pop("headers", {})
            headers = {**common_headers(), **headers}
            assert self._client is not None
            r = await self._client.get(url, headers=headers, **kwargs)
            if r.status_code in (429, 503):
                raise BlockedError(f"{r.status_code} on {url}")
            if r.status_code == 403:
                raise BlockedError(f"403 on {url}")
            r.raise_for_status()
            if self._is_captcha(r.text):
                raise BlockedError(f"captcha detected at {url}")
            return r

    def _is_captcha(self, html: str) -> bool:
        markers = ("captcha", "Robot Check", "/errors/validateCaptcha", "Enter the characters you see")
        return any(m.lower() in html.lower()[:5000] for m in markers)

    async def search(self, category: str, subcategory: str, query: str,
                     is_smart: bool, top_n: int) -> List[Product]:
        raise NotImplementedError

    async def fetch_reviews(self, sku: str, top_n: int) -> List[Review]:
        return []

    def save_raw(self, kind: str, query: str, payload):
        outdir = DATA_ROOT / "raw" / self.platform
        outdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_query = query.replace(" ", "_").replace("/", "-")
        fp = outdir / f"{kind}_{safe_query}_{ts}.json"
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        return fp


def parse_price(text):
    """从字符串里抠出价格数字和原始字符串"""
    if not text:
        return None, None
    text = text.strip()
    import re
    m = re.search(r"[\$€£¥]?\s*([\d,]+(?:\.\d+)?)", text.replace(",", ""))
    if not m:
        return None, text
    try:
        return float(m.group(1)), text
    except ValueError:
        return None, text


def parse_int(text):
    if not text:
        return None
    import re
    text = text.replace(",", "")
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def estimate_sold_from_reviews(review_count):
    """行业经验：评论数大约是销量的 1-3%"""
    if review_count is None:
        return None
    return int(review_count / 0.02)
