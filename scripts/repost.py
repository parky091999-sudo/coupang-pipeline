"""
특정 상품 코드의 Threads 포스팅을 이미지와 함께 재포스팅.
- 기존 Threads 포스트 삭제
- 이미지 없으면 네이버 쇼핑에서 보충
- Gemini로 이미지 4종 생성 → imgBB 업로드
- Threads에 carousel 재게시
- feed_posts.json, product_registry.json 업데이트
- GitHub Pages 재생성

사용법: python scripts/repost.py <code>
예시:   python scripts/repost.py 010
        python scripts/repost.py 013
"""
import json
import logging
import os
import subprocess
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from config import THREADS_ACCESS_TOKEN, THREADS_USER_ID

DATA_DIR = os.path.join(ROOT, "data")
FEED_PATH = os.path.join(DATA_DIR, "feed_posts.json")
REGISTRY_PATH = os.path.join(DATA_DIR, "product_registry.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("repost")

GRAPH_BASE = "https://graph.threads.net/v1.0"


# ── 유틸 ───────────────────────────────────────────────────────────────────

def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _threads_get(path, **params):
    params["access_token"] = THREADS_ACCESS_TOKEN
    r = requests.get(f"{GRAPH_BASE}{path}", params=params, timeout=30)
    return r.json()

def _threads_delete(post_id: str) -> bool:
    r = requests.delete(
        f"{GRAPH_BASE}/{post_id}",
        params={"access_token": THREADS_ACCESS_TOKEN},
        timeout=30,
    )
    d = r.json()
    return bool(d.get("success") or d.get("deleted"))

def _get_numeric_id_from_url(post_url: str) -> str | None:
    """permalink URL에서 numeric post ID 조회"""
    if not post_url or "/post/" not in post_url:
        return None
    url_code = post_url.split("/post/")[-1].strip("/")
    try:
        data = _threads_get(
            f"/{THREADS_USER_ID}/threads",
            fields="id,permalink",
            limit=50,
        )
        for p in data.get("data", []):
            plink = p.get("permalink", "")
            if url_code in plink:
                return p.get("id")
    except Exception as e:
        logger.warning(f"numeric ID 조회 실패: {e}")
    return None


# ── 메인 ───────────────────────────────────────────────────────────────────

def repost(code: str):
    code = code.zfill(3)
    logger.info(f"=== [{code}] 재포스팅 시작 ===")

    # 1. feed에서 포스팅 정보 읽기
    feed = _load_json(FEED_PATH)
    feed_entry = next((p for p in feed if p.get("product_code") == code), None)
    if not feed_entry:
        logger.error(f"feed_posts.json에 [{code}] 항목 없음")
        sys.exit(1)

    post_text    = feed_entry.get("post_text", "")
    product_url  = feed_entry.get("product_url", "")
    product_name = feed_entry.get("product_name", "")
    old_threads_url = feed_entry.get("threads_url", "")

    # 2. registry에서 image_url 읽기
    reg = _load_json(REGISTRY_PATH)
    reg_key = (product_url or "")[:80]
    reg_entry = reg["products"].get(reg_key, {})
    image_url = reg_entry.get("image_url", "") or feed_entry.get("product_image", "")

    # 3. 이미지 없으면 네이버로 보충
    if not image_url and product_name:
        logger.info(f"  이미지 없음 → 네이버 쇼핑 검색: {product_name[:30]}")
        from scraper.naver_shopping import fetch_image_by_name
        image_url = fetch_image_by_name(product_name)
        if image_url:
            logger.info(f"  네이버 이미지 확보: {image_url[:60]}")
            # registry에 저장
            if reg_key in reg["products"]:
                reg["products"][reg_key]["image_url"] = image_url
                _save_json(REGISTRY_PATH, reg)
            # feed에도 저장
            feed_entry["product_image"] = image_url
        else:
            logger.warning("  네이버 이미지 보충 실패 — 텍스트 전용 재시도")

    # 4. Gemini 이미지 생성
    detail_images = []
    if image_url:
        logger.info("  Gemini 이미지 생성 중 (4종)...")
        from generator.image_gen import generate_and_upload_images
        product_dict = {"image_url": image_url, "name": product_name}
        detail_images = generate_and_upload_images(product_dict, post_text)
        logger.info(f"  Gemini 이미지 {len(detail_images)}장 준비")

    # 5. 기존 Threads 포스트 삭제
    if old_threads_url:
        logger.info(f"  기존 포스트 삭제 중: {old_threads_url}")
        numeric_id = _get_numeric_id_from_url(old_threads_url)
        if numeric_id:
            ok = _threads_delete(numeric_id)
            if ok:
                logger.info(f"  삭제 완료 (ID: {numeric_id})")
            else:
                logger.warning(f"  삭제 실패 또는 이미 삭제됨 (ID: {numeric_id})")
        else:
            logger.warning(f"  numeric ID 조회 실패 — 삭제 건너뜀")
    time.sleep(5)

    # 6. 재게시
    logger.info("  Threads 재게시 중...")
    from poster.threads import post_thread_api
    result = post_thread_api(
        post_text=post_text,
        image_url=image_url or None,
        detail_images=detail_images if detail_images else None,
        fallback_image_url=image_url or None,
    )
    if not result:
        logger.error("  재게시 실패")
        sys.exit(1)

    new_post_id  = result.get("post_id", "")
    new_post_url = result.get("post_url", "")
    logger.info(f"  재게시 완료: {new_post_url}")

    # 7. feed_posts.json 업데이트
    feed_entry["threads_url"] = new_post_url
    if image_url:
        feed_entry["product_image"] = image_url
    _save_json(FEED_PATH, feed)
    logger.info("  feed_posts.json 업데이트")

    # 8. GitHub Pages 재생성
    logger.info("  페이지 재생성 중...")
    subprocess.run([sys.executable, os.path.join(ROOT, "generate_page.py")], check=True)
    logger.info(f"=== [{code}] 재포스팅 완료 ===")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/repost.py <code>")
        print("예시:   python scripts/repost.py 010")
        sys.exit(1)
    repost(sys.argv[1])
