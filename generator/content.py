"""
콘텐츠 생성기
- 글1: Groq AI로 상품별 맞춤 생성 (스토리텔링 + 해시태그)
- 글2: 코드 기반 유도 — URL 직접 노출 없음 ("프로필 링크에서 [CODE] 검색")
- COUPANG_PARTNERS_ACTIVE=True 시 [광고] + 공정위 고지문 자동 추가
"""
import random
import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import COUPANG_PARTNERS_ACTIVE, GROQ_API_KEY

logger = logging.getLogger(__name__)

_AD_DISCLOSURE = "이 게시물은 쿠팡파트너스 활동의 일환으로 수수료를 받을 수 있습니다"


# ── 글1: Groq AI 생성 ────────────────────────────────────────────────────────

_POST1_SYSTEM = """
너는 Threads SNS에서 신기한 생활용품을 소개하는 일반 사용자야.
계정 컨셉: "보다가 이게 뭐야 싶은 것들만" 올리는 계정.

출력 형식 (반드시 이 순서, 빈 줄로 구분):
[본문 2~4줄]

[해시태그 한 줄, 3~5개]

본문 작성 규칙:
- 반말, 친근하고 자연스럽게
- 상품의 실제 특징이나 쓰임새를 구체적으로 언급
- 처음 봤을 때 신기하거나 "이게 돼?" 싶은 반응 유도
- 광고·홍보 느낌 없게. 가격 언급 금지
해시태그 예시: #생활꿀템 #주방템 #살림템 #아이디어상품 #주부템

텍스트만 출력. 설명, 따옴표, 코드 안내 문구 넣지 말 것.
""".strip()

_CODE_LINE = "제품 정보는 프로필 링크에서 [{code}]을 검색해보세요 👇"


def _generate_post1_ai(product: dict, product_code: str) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        name = product.get("name", "")
        category_hint = product.get("category_hint", "")
        brand = product.get("brand", "")
        yt = product.get("youtube_source", {})

        user_msg = f"상품명: {name}"
        if brand:
            user_msg += f"\n브랜드: {brand}"
        if category_hint:
            user_msg += f"\n카테고리: {category_hint}"
        if yt.get("title"):
            user_msg += f"\n참고 유튜브 제목: {yt['title'][:60]}"
        user_msg += "\n\n위 상품 소개 게시글을 써줘."

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _POST1_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=200,
            temperature=0.85,
        )
        body_and_tags = resp.choices[0].message.content.strip().strip('"\'""''')
        if not body_and_tags:
            return None
        # 코드 안내 첫 줄 + 빈 줄 + AI 생성 본문+해시태그
        return f"{_CODE_LINE.format(code=product_code)}\n\n{body_and_tags}"
    except Exception as e:
        logger.warning(f"AI 글1 생성 실패: {e}")
        return None


# ── 글1: 폴백 템플릿 ──────────────────────────────────────────────────────────

def _post1_fallback(name: str, product_code: str) -> str:
    short = name[:28] + ("..." if len(name) > 28 else "")
    variations = [
        f"이거 처음 봤을 때 진짜 뭔지 몰랐음\n써보니까 없으면 안 되겠더라\n{short}\n\n#생활꿀템 #살림템 #아이디어상품",
        f"이런 게 있다는 걸 오늘 알았음\n진짜 신기해서 한참 봄\n{short}\n\n#생활꿀템 #주방템 #꿀템",
        f"이거 본 적 있어?\n존재 자체가 신기한 물건\n{short}\n\n#아이디어상품 #생활꿀템 #살림",
    ]
    body_and_tags = random.choice(variations)
    return f"{_CODE_LINE.format(code=product_code)}\n\n{body_and_tags}"


# ── 메인 생성 함수 ─────────────────────────────────────────────────────────────

def generate_post(product: dict) -> dict:
    from generator.registry import assign_code

    name = product.get("name", "")
    product_url = product.get("product_url", "")
    image_url = product.get("image_url", "")

    # 상품 코드 할당 ([001], [002]...)
    product_code = assign_code(product_url, name, image_url)

    # 글1 하나만 — 스토리 + 해시태그 + 코드 안내 통합
    post_text_1 = _generate_post1_ai(product, product_code)
    if post_text_1:
        style = "ai"
    else:
        post_text_1 = _post1_fallback(name, product_code)
        style = "fallback"

    if COUPANG_PARTNERS_ACTIVE:
        post_text_1 = f"[광고]\n{post_text_1}\n\n{_AD_DISCLOSURE}"

    logger.info(f"생성 완료 [{style}][{product_code}]: {name[:30]}")
    return {
        "post_text_1": post_text_1,
        "post_text_2": "",          # 글2 없음
        "image_url": image_url,
        "product": product,
        "style": style,
        "product_code": product_code,
    }


def generate_posts_batch(products: list[dict]) -> list[dict]:
    results = []
    for product in products:
        try:
            results.append(generate_post(product))
        except Exception as e:
            logger.error(f"콘텐츠 생성 실패: {e}")
    return results
