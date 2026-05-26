"""
콘텐츠 생성기 - 쓰레드 스타일 (반말, 자연스러운 말투)
여러 스타일 버전을 랜덤으로 섞어서 A/B 테스트용으로 활용
"""
import random
import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

logger = logging.getLogger(__name__)


def _parse_price(price_str: str) -> int:
    try:
        return int("".join(filter(str.isdigit, price_str)))
    except Exception:
        return 0


def _saved_str(original_price: str, price: str) -> str:
    orig = _parse_price(original_price)
    cur = _parse_price(price)
    if orig > cur > 0:
        return f"{orig - cur:,}원"
    return ""


# ── 스타일 A: 친구한테 말하듯 ───────────────────────────────────────────
def _style_friend(name: str, price: str, original_price: str, discount_rate: int) -> str:
    saved = _saved_str(original_price, price)
    short_name = name[:30] + ("..." if len(name) > 30 else "")

    if saved and discount_rate > 0:
        variations = [
            f"야 이거 봐\n\n{short_name}\n지금 {discount_rate}% 할인하는데 {price}이야\n\n나 이거 샀는데 진짜 좋음",
            f"이거 쓰는 사람 있어?\n\n{short_name}\n{price}인데 원래 {original_price}였거든\n{saved} 아끼는 거잖아 이게",
            f"오늘 이거 발견했는데\n\n{short_name}\n{discount_rate}% 할인 중이래\n솔직히 이 가격이면 살만하지 않음?",
        ]
    else:
        variations = [
            f"야 이거 봐\n\n{short_name}\n지금 {price}이야\n\n나쁘지 않지 않음?",
            f"이거 어때\n\n{short_name}\n{price}에 팔고 있던데\n요즘 이 가격 보기 쉽지 않더라",
            f"오늘 이거 발견했는데\n\n{short_name}\n{price}\n솔직히 이 가격이면 살만하지 않음?",
        ]
    return random.choice(variations)


# ── 스타일 B: 혼잣말 관찰 형식 ──────────────────────────────────────────
def _style_observation(name: str, price: str, original_price: str, discount_rate: int) -> str:
    saved = _saved_str(original_price, price)
    short_name = name[:30] + ("..." if len(name) > 30 else "")

    if saved and discount_rate > 0:
        variations = [
            f"쿠팡 보다가 발견함\n\n{short_name}\n{price} ← 이 가격 실화?\n\n{discount_rate}% 할인이면 {saved} 아끼는 건데",
            f"아 이거 괜찮다\n\n{short_name}\n{price}에 팔고 있음\n원래 {original_price}짜리인데 지금 내림",
            f"오늘의 발견\n\n{short_name}\n{price} / {discount_rate}% 할인\n\n사야 하나 고민 중",
        ]
    else:
        variations = [
            f"쇼핑하다가 발견함\n\n{short_name}\n{price} ← 이 가격 실화?",
            f"아 이거 괜찮은데\n\n{short_name}\n지금 {price}임\n필요한 사람 참고해",
            f"오늘의 발견\n\n{short_name}\n{price}\n\n사야 하나 고민 중",
        ]
    return random.choice(variations)


# ── 스타일 C: 짧고 직관적 ────────────────────────────────────────────────
def _style_short(name: str, price: str, original_price: str, discount_rate: int) -> str:
    saved = _saved_str(original_price, price)
    short_name = name[:25] + ("..." if len(name) > 25 else "")

    if discount_rate > 0:
        variations = [
            f"{short_name}\n\n{price} ({discount_rate}% 할인)\n\n이 가격 맞음?",
            f"지금 {discount_rate}% 할인\n\n{short_name}\n{price}" + (f"\n\n{saved} 이득" if saved else ""),
            f"오늘만 이 가격인지 모르겠는데\n\n{short_name}\n{price}",
        ]
    else:
        variations = [
            f"{short_name}\n\n{price}\n\n이 가격 맞음?",
            f"가격 보고 두 번 봤음\n\n{short_name}\n{price}",
            f"오늘 발견한 거\n\n{short_name}\n{price}",
        ]
    return random.choice(variations)


# ── 스타일 D: 공감 + 정보형 ──────────────────────────────────────────────
def _style_empathy(name: str, price: str, original_price: str, discount_rate: int) -> str:
    saved = _saved_str(original_price, price)
    short_name = name[:30] + ("..." if len(name) > 30 else "")

    if discount_rate > 0:
        variations = [
            f"요즘 물가 미쳤는데\n\n{short_name} {price}면 그나마 숨통 트이지 않음\n{discount_rate}% 할인 중이래",
            f"집에 하나 있으면 편한데 비싸서 못 샀었는데\n\n{short_name}\n지금 {price}임 ({discount_rate}% 할인)" + (f"\n{saved} 아끼는 거라고" if saved else ""),
            f"이거 써본 사람 있어?\n\n{short_name}\n{price}인데 리뷰가 괜찮던데\n{discount_rate}% 할인 중이라 고민 됨",
        ]
    else:
        variations = [
            f"요즘 물가 미쳤는데\n\n{short_name}\n{price}면 그나마 숨통 트이지 않음?",
            f"은근 필요한데 맨날 미뤘던 거\n\n{short_name}\n지금 {price}임\n이 참에 사볼까 고민 중",
            f"이거 써본 사람 있어?\n\n{short_name}\n{price}인데 리뷰가 괜찮던데",
        ]
    return random.choice(variations)


# ── 해시태그 ─────────────────────────────────────────────────────────────
HASHTAG_SETS = [
    "#쿠팡 #할인 #핫딜",
    "#쿠팡핫딜 #특가",
    "#오늘특가 #쿠팡",
    "#할인정보 #핫딜",
    "#쿠팡 #득템",
    "",  # 해시태그 없는 버전도 테스트
    "",
]

STYLE_FUNCS = [_style_friend, _style_observation, _style_short, _style_empathy]
STYLE_NAMES = ["friend", "observation", "short", "empathy"]


def generate_post(product: dict) -> dict:
    name = product.get("name", "")
    price = product.get("price", "")
    original_price = product.get("original_price", price)
    discount_rate = product.get("discount_rate", 0)
    product_url = product.get("product_url", "")

    style_fn = random.choice(STYLE_FUNCS)
    style_name = STYLE_NAMES[STYLE_FUNCS.index(style_fn)]
    body = style_fn(name, price, original_price, discount_rate)

    tags = random.choice(HASHTAG_SETS)
    post_text = f"{body}\n\n{tags}".strip() if tags else body

    comment_text = _build_comment(product_url, discount_rate, price)

    logger.info(f"생성 완료 [{style_name}]: {name[:30]}")
    return {
        "post_text": post_text,
        "comment_text": comment_text,
        "product": product,
        "style": style_name,
    }


def _build_comment(product_url: str, discount_rate: int, price: str) -> str:
    if not product_url:
        return ""
    return "\n".join([
        "구매링크",
        product_url,
        "",
        "파트너스 활동으로 수수료를 받을 수 있어요",
    ])


def generate_posts_batch(products: list[dict]) -> list[dict]:
    results = []
    for product in products:
        try:
            result = generate_post(product)
            results.append(result)
        except Exception as e:
            logger.error(f"콘텐츠 생성 실패: {e}")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_product = {
        "name": "삼성 갤럭시 버즈3 프로 블루투스 이어폰 노이즈캔슬링",
        "price": "139,000원",
        "original_price": "259,000원",
        "discount_rate": 46,
        "product_url": "https://www.coupang.com/vp/products/test123",
    }
    print("=== 4가지 스타일 미리보기 ===\n")
    for fn, name in zip(STYLE_FUNCS, STYLE_NAMES):
        print(f"── [{name}] ──")
        body = fn(
            test_product["name"],
            test_product["price"],
            test_product["original_price"],
            test_product["discount_rate"],
        )
        tags = random.choice(HASHTAG_SETS)
        print(body + (f"\n\n{tags}" if tags else ""))
        print()
