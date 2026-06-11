"""
coupang_images.py
쿠팡 상품 페이지에서 상세 이미지 3~4장 추출
- 대표 썸네일이 아닌, 상세페이지 갤러리 이미지 사용
- 감성/제품컷 위주로 수집해 Threads carousel에 사용

주의: Coupang은 JavaScript로 이미지를 동적 로드하므로, requests + BeautifulSoup으로는
gallery 이미지를 가져올 수 없음. og:image 폴백만 작동.
실제 gallery 이미지를 원하면 Playwright/Selenium 필요 (GitHub Actions에서는 느림)
"""
import re
import time
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]

def _get_headers():
    import random
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }

# 이미지 URL에서 제외할 패턴 (아이콘/배너/로고 등)
_SKIP_PATTERNS = [
    "logo", "banner", "icon", "badge", "button",
    "arrow", "star", "rating", "review",
    "gift", "coupon", "event",
]

# 중국어 CDN 도메인 — 중국어 텍스트 삽입된 이미지 출처
_CHINESE_CDN_PATTERNS = [
    "alicdn.com", "taobao.com", "tmall.com",
    "jd.com", "jdcloud.com", "kaola.com",
    "pinduoduo.com", "shopee.com",
    "img.gg.com", "gooood.cn",
]


def fetch_product_images(product_url: str, max_images: int = 4) -> list[str]:
    """
    쿠팡 상품 URL → 갤러리 이미지 URL 리스트 반환 (최대 max_images장)

    우선순위:
    1. ol.prod-img-list (상품 갤러리 썸네일)
    2. window.__PRELOADED_STATE__ JSON 내 imageList
    3. og:image (최후 폴백)
    """
    if not product_url or "coupang.com" not in product_url:
        return []

    # 네이버 → 쿠팡 리다이렉트 추적
    final_url = _resolve_redirect(product_url)
    if not final_url:
        return []

    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(1.5)  # 쿠팡 봇 감지 방지
            resp = requests.get(final_url, headers=_get_headers(), timeout=12)

            if resp.status_code == 403:
                if attempt < max_retries - 1:
                    logger.warning(f"403 차단 (시도 {attempt+1}/{max_retries}) → 재시도 중...")
                    time.sleep(2)
                    continue
                else:
                    logger.warning(f"쿠팡 페이지 접근 차단 (403): {final_url[:60]}")
                    return []

            if resp.status_code != 200:
                logger.warning(f"쿠팡 페이지 {resp.status_code}: {final_url[:60]}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            images: list[str] = []

            # ── 방법 1: 상품 갤러리 썸네일 리스트 ───────────────────────────────
            gallery = soup.select("ol.prod-img-list li img, ul.prod-img-list li img")
            for img in gallery:
                src = img.get("src") or img.get("data-src") or ""
                src = _upgrade_image_url(src)
                if src and _is_valid_image(src) and src not in images:
                    images.append(src)
                if len(images) >= max_images:
                    break

            # ── 방법 2: JSON 내 imageList 파싱 ──────────────────────────────────
            if len(images) < 2:
                json_images = _extract_from_json(resp.text)
                for url in json_images:
                    if url not in images:
                        images.append(url)
                    if len(images) >= max_images:
                        break

            # ── 방법 3: og:image 폴백 ────────────────────────────────────────────
            if not images:
                og = soup.find("meta", property="og:image")
                if og and og.get("content"):
                    src = _upgrade_image_url(og["content"])
                    if src:
                        images.append(src)

            logger.info(f"이미지 {len(images)}장 수집 완료: {final_url[:50]}")
            return images[:max_images]

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"이미지 수집 오류 (시도 {attempt+1}/{max_retries}): {e}")
                time.sleep(2)
                continue
            else:
                logger.warning(f"이미지 수집 최종 실패: {e}")
                return []


def _resolve_redirect(url: str) -> str | None:
    """네이버 쇼핑 단축 URL → 실제 쿠팡 URL 추적"""
    try:
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        final = resp.url
        if "coupang.com" in final:
            return final
        # HEAD가 막힌 경우 GET으로 재시도
        resp = requests.get(
            url,
            allow_redirects=True,
            timeout=8,
            headers=HEADERS,
        )
        if "coupang.com" in resp.url:
            return resp.url
        return None
    except Exception as e:
        logger.warning(f"리다이렉트 추적 실패: {e}")
        return None


def _extract_from_json(html: str) -> list[str]:
    """HTML 내 JSON 데이터에서 이미지 URL 추출"""
    images = []
    # imageList, imageUrl, vendorItemImages 등 패턴 매칭
    patterns = [
        r'"imageList"\s*:\s*\[(.*?)\]',
        r'"vendorItemImages"\s*:\s*\[(.*?)\]',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            urls = re.findall(r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', m.group(1))
            for url in urls:
                url = _upgrade_image_url(url)
                if url and _is_valid_image(url) and url not in images:
                    images.append(url)

    # 개별 imageUrl 필드 (중복 없이 추가)
    if not images:
        urls = re.findall(r'"imageUrl"\s*:\s*"(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html)
        seen = set()
        for url in urls:
            url = _upgrade_image_url(url)
            if url and _is_valid_image(url) and url not in seen:
                seen.add(url)
                images.append(url)

    return images


def _upgrade_image_url(url: str) -> str:
    """
    쿠팡 이미지 URL을 고해상도로 업그레이드
    - http → https
    - 쿼리스트링 제거
    - 썸네일 사이즈 파라미터 제거
    """
    if not url:
        return ""
    url = url.strip()
    url = url.replace("http://", "https://")
    # 쿼리스트링 제거
    url = url.split("?")[0]
    # 저해상도 패턴 교체 (/q70/80x80/ → /q85/)
    url = re.sub(r"/q\d+/\d+x\d+/", "/q85/", url)
    # 아주 작은 사이즈 파라미터 제거
    url = re.sub(r"_\d{2,3}x\d{2,3}\.", ".", url)
    return url


def _is_valid_image(url: str) -> bool:
    """아이콘/배너/로고/중국 CDN 이미지 제외"""
    url_lower = url.lower()
    if len(url) < 20:
        return False
    if any(p in url_lower for p in _SKIP_PATTERNS):
        return False
    if any(p in url_lower for p in _CHINESE_CDN_PATTERNS):
        logger.info(f"  중국 CDN 이미지 제외: {url[:60]}")
        return False
    if not re.search(r"\.(jpg|jpeg|png|webp)", url_lower):
        return False
    return True
