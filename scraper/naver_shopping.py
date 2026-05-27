"""
네이버 쇼핑 API 스크래퍼
- 뷰티 키워드 검색으로 할인 상품 수집
- 무료 25,000건/일 (네이버 개발자센터 앱 등록 필요)
- 할인율: hprice(최고가) vs lprice(최저가) 차이로 근사 계산
"""
import requests
import logging
import sys
import os
import json
import re
from datetime import datetime
from itertools import cycle

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import (
    DATA_DIR, MAX_PRODUCTS_PER_RUN,
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
)

logger = logging.getLogger(__name__)

API_URL = "https://openapi.naver.com/v1/search/shop.json"

# 카테고리별 키워드 — (키워드, 카테고리힌트) 튜플
# 전략: 싸고 좋은 상품 X → 피드에서 "이게 뭐야?" 반응 나오는 상품 O
# 기준: 보는 순간 신기하거나 웃기거나 공감되는 것
SEARCH_KEYWORDS = [
    # 전동/자동 가젯 — 평범한 것의 전동화된 버전은 항상 신기함
    ("전동 안마기 가정용", "생활"),
    ("자동 주방 도구", "생활"),
    ("전동 청소 도구", "생활"),
    ("자동 반려동물 장난감", "반려동물"),
    # 스트레스 해소 / 운동 — 집에서 혼자 쓰는 특이한 운동기구
    ("복싱 샌드백 가정용", "생활"),
    ("스트레스 해소 장난감 성인", "생활"),
    ("진동 마사지기 목", "생활"),
    ("허리 마사지 의자", "생활"),
    # 반려동물 — 동물 반응 영상은 항상 바이럴
    ("고양이 자동 장난감", "반려동물"),
    ("강아지 재미있는 장난감", "반려동물"),
    # 수면 / 건강 — 고민 있는 사람들이 많아서 공감 폭발
    ("코골이 방지 용품", "생활"),
    ("수면 안대 신기한", "생활"),
    # 주방 / 식탁 — 유튜브 쇼핑 영상에 자주 나오는 유형
    ("전동 와인오프너", "생활"),
    ("아보카도 커터 주방", "생활"),
    ("진공 보관 용기 전동", "생활"),
    # 욕실 / 뷰티 가젯
    ("전동 세안기 클렌저", "생활"),
    ("피부 관리 LED 마스크", "생활"),
]

MIN_LPRICE = 15_000  # 15,000원 미만 단순 소품 제외

# 같은 배치 내 중복 방지 — 같은 그룹 키워드가 상품명에 있으면 동일 유형으로 판단
# 한 배치에서 같은 유형은 1개만 허용
_TYPE_GROUPS: list[list[str]] = [
    ["led마스크", "led 마스크", "피부관리기", "피부 관리 led", "led피부관리"],
    ["마사지의자", "안마의자", "마사지 의자"],
    ["안마기", "마사지기", "마사지건", "마사지 건"],
    ["공기청정기"],
    ["로봇청소기", "청소기"],
    ["에어프라이어"],
    ["가습기"],
    ["제습기"],
    ["선풍기", "써큘레이터"],
    ["블루투스 스피커", "블루투스스피커"],
    ["반려동물 자동", "고양이 자동", "강아지 자동"],
    ["코골이"],
]


def _get_product_type(name: str) -> str | None:
    """상품명에서 유형 ID 추출 — 같은 유형이면 같은 문자열 반환"""
    name_lower = name.lower().replace(" ", "")
    for group in _TYPE_GROUPS:
        for kw in group:
            if kw.replace(" ", "") in name_lower:
                return group[0]
    return None


# 상품명에서 제거할 광고성/불필요 패턴
_NAME_NOISE = re.compile(
    r"(\[.*?\])"                   # [특가] [타임딜] 등 대괄호 문구
    r"|(\(.*?직영.*?\))"           # (본사직영) 등
    r"|(,\s*\d+개$)"               # 끝의 수량 표기 ",  1개"
    r"|(\s{2,})",                  # 연속 공백
    re.IGNORECASE,
)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _clean_name(name: str) -> str:
    """상품명에서 광고성 문구 제거"""
    cleaned = _NAME_NOISE.sub(" ", name).strip()
    # 앞뒤 특수문자 정리
    cleaned = re.sub(r"^[\s\-_,/|]+|[\s\-_,/|]+$", "", cleaned)
    return cleaned if cleaned else name


def _fetch_items(keyword: str, display: int = 30) -> list[dict]:
    """네이버 쇼핑 API 호출"""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": display, "sort": "sim"}
    resp = requests.get(API_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("items", [])


def _calc_discount_rate(lprice: int, hprice: int) -> int:
    """최고가 대비 최저가 할인율"""
    if hprice > 0 and lprice > 0 and hprice > lprice:
        return round((1 - lprice / hprice) * 100)
    return 0


def _is_bad_name(name: str) -> bool:
    """중국산 키워드 도배 상품명 감지 — 단어 수 많고 의미 없는 수식어 나열"""
    words = name.split()
    # 단어 10개 이상이면 키워드 스터핑 의심
    if len(words) >= 10:
        return True
    # 색상+소재+용도+수량 다 때려박은 패턴 (예: "블랙을", "소 실버 1개")
    noise_patterns = ["블랙을", "실버 1개", "블루를", "화이트를", "측정기용"]
    if any(p in name for p in noise_patterns):
        return True
    return False


def _to_product(item: dict, category_hint: str = "") -> dict | None:
    """네이버 API 응답 → 파이프라인 공통 포맷"""
    raw_name = _strip_html(item.get("title", ""))
    if not raw_name:
        return None

    name = _clean_name(raw_name)

    if _is_bad_name(name):
        return None

    lprice = int(item.get("lprice", 0) or 0)
    hprice = int(item.get("hprice", 0) or 0)

    if lprice < MIN_LPRICE:
        return None

    discount_rate = _calc_discount_rate(lprice, hprice)

    return {
        "name": name,
        "price": f"{lprice:,}원",
        "original_price": f"{hprice:,}원" if hprice else "",
        "discount_rate": discount_rate,
        "image_url": item.get("image", ""),
        "product_url": item.get("link", ""),
        "badge": item.get("mallName", ""),
        "brand": item.get("brand", ""),
        "category": item.get("category3", item.get("category2", "")),
        "category_hint": category_hint,
        "mall_name": item.get("mallName", ""),
        "source": "naver_shopping",
        "scraped_at": datetime.now().isoformat(),
    }


def scrape_deals(max_items: int = MAX_PRODUCTS_PER_RUN) -> list[dict]:
    """상품 수집 (네이버 쇼핑 API) — 다양한 카테고리, 쿠팡 판매 상품 우선"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        logger.error("네이버 API 키 미설정 — .env에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 추가 필요")
        return []

    coupang_products: list[dict] = []
    all_products: list[dict] = []
    seen_names: set[str] = set()
    seen_types: set[str] = set()  # 유형 중복 방지

    for keyword, cat_hint in SEARCH_KEYWORDS:
        if len(coupang_products) >= max_items:
            break
        try:
            logger.info(f"네이버 쇼핑 검색: '{keyword}'")
            items = _fetch_items(keyword)
            logger.info(f"  → {len(items)}개 항목 수신")

            for item in items:
                product = _to_product(item, category_hint=cat_hint)
                if not product:
                    continue
                # 상품명 중복 제거
                key = product["name"][:8]
                if key in seen_names:
                    continue
                seen_names.add(key)

                is_coupang = "쿠팡" in product["mall_name"]
                if is_coupang:
                    # 유형 중복 제거 — 쿠팡 상품끼리만 비교 (비쿠팡이 슬롯 차지 방지)
                    ptype = _get_product_type(product["name"])
                    if ptype and ptype in seen_types:
                        logger.info(f"  유형 중복 제외 [{ptype}]: {product['name'][:30]}")
                        continue
                    if ptype:
                        seen_types.add(ptype)
                    coupang_products.append(product)
                    logger.info(f"  [쿠팡/{cat_hint}] {product['name'][:40]} | {product['price']}")
                else:
                    all_products.append(product)

        except requests.HTTPError as e:
            logger.error(f"API 오류 ({keyword}): {e}")
            break
        except Exception as e:
            logger.warning(f"키워드 오류 ({keyword}): {e}")

    result = coupang_products[:max_items]
    logger.info(f"최종 수집: {len(result)}개 (쿠팡만)")
    return result


# 하위 호환용 alias
scrape_beauty_deals = scrape_deals


def save_products(products: list[dict], filename: str = "products.json"):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    logger.info(f"저장: {path}")
    return path


def load_products(filename: str = "products.json") -> list[dict]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def run():
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    products = scrape_beauty_deals()
    if products:
        save_products(products)
        print(f"\n수집된 뷰티 상품 {len(products)}개:")
        for p in products:
            print(f"  [{p['discount_rate']}%] {p['name'][:45]} | {p['price']} | {p['mall_name']}")
    else:
        print("수집된 상품이 없습니다.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
