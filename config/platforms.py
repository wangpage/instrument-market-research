PLATFORMS = {
    "amazon": {
        "search_url": "https://www.amazon.com/s",
        "search_param": "k",
        "needs_browser": False,
        "delay_range": (4, 9),
        "max_concurrency": 2,
    },
    "ebay": {
        "search_url": "https://api.ebay.com/buy/browse/v1/item_summary/search",
        "fallback_search_url": "https://www.ebay.com/sch/i.html",
        "needs_browser": False,
        "delay_range": (1, 3),
        "max_concurrency": 5,
    },
    "walmart": {
        "search_url": "https://www.walmart.com/search",
        "needs_browser": True,
        "delay_range": (3, 7),
        "max_concurrency": 1,
    },
    "tiktok_shop": {
        "search_url": "https://www.tiktok.com/shop/s/{query}",
        "fallback_url": "https://www.fastmoss.com/e-commerce/detail",
        "needs_browser": True,
        "delay_range": (5, 12),
        "max_concurrency": 1,
    },
    "temu": {
        "search_url": "https://www.temu.com/search_result.html",
        "needs_browser": True,
        "delay_range": (3, 8),
        "max_concurrency": 1,
    },
}


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


def common_headers(ua=None):
    import random
    return {
        "User-Agent": ua or random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
