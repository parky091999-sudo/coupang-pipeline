"""YouTube 트렌딩 상품 탐지 테스트"""
import logging
import sys
import os

sys.path.append(os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

from config import YOUTUBE_API_KEY

if not YOUTUBE_API_KEY:
    print("❌ YOUTUBE_API_KEY가 .env에 없습니다.")
    print("   Google Cloud Console에서 YouTube Data API v3 키를 발급받아 .env에 추가하세요.")
    sys.exit(1)

from scraper.youtube_trending import scrape_trending_products

print("=" * 60)
print("YouTube 트렌딩 상품 탐지 테스트")
print("=" * 60)

products = scrape_trending_products(max_items=5)

print(f"\n수집 결과: {len(products)}개\n")
for i, p in enumerate(products, 1):
    yt = p.get("youtube_source", {})
    print(f"[{i}] {p['name'][:50]}")
    print(f"     가격: {p['price']} | 쇼핑몰: {p.get('mall_name', '-')}")
    if yt:
        safe_title = yt['title'].encode('cp949', errors='ignore').decode('cp949')
        print(f"     [YouTube] {safe_title[:50]} ({yt['views']:,}회)")
    print()
