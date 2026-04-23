from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


class Product(BaseModel):
    platform: str
    query_keyword: str
    category: str
    subcategory: str
    rank_in_search: int

    title: str
    brand: Optional[str] = None
    asin_or_sku: str
    url: str
    image_url: Optional[str] = None

    price_usd: Optional[float] = None
    original_price_usd: Optional[float] = None
    currency_raw: Optional[str] = None
    price_raw: Optional[str] = None

    rating: Optional[float] = None
    review_count: Optional[int] = None
    sold_count_text: Optional[str] = None
    sold_count_estimated: Optional[int] = None

    bsr_rank: Optional[int] = None
    bsr_category: Optional[str] = None

    seller_name: Optional[str] = None
    seller_country: Optional[str] = None
    shipping_info: Optional[str] = None
    listing_date: Optional[str] = None

    is_smart_instrument: bool = False
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class Review(BaseModel):
    platform: str
    asin_or_sku: str
    review_id: str

    author: Optional[str] = None
    rating: Optional[float] = None
    date: Optional[str] = None

    title: Optional[str] = None
    body: str
    helpful_count: Optional[int] = None
    verified_purchase: Optional[bool] = None

    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackPoint(BaseModel):
    point: str
    frequency: int
    sample_quote: str


class ReviewSummary(BaseModel):
    asin_or_sku: str
    platform: str
    total_reviews_analyzed: int
    top_praise_points: List[FeedbackPoint] = Field(default_factory=list)
    top_complaint_points: List[FeedbackPoint] = Field(default_factory=list)
    overall_sentiment_score: Optional[float] = None
