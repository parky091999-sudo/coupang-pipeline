"""
쿠팡 파트너스 링크 무결성 검증.

product_registry.json의 모든 상품 URL에 GET 요청 후 리다이렉트 최종 목적지를 확인.
- /vp/products/  → 살아있음 (OK)
- 홈페이지/404   → 단종 의심 (DEAD)
- 오류           → 확인불가 (ERROR)

removed: true 상품은 건너뜀.
"""
import io
import json
import os
import sys
import time

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(__file__))
REGISTRY_PATH = os.path.join(ROOT, "data", "product_registry.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEAD_SIGNALS = [
    "coupang.com/?",            # 홈으로 리다이렉트
    "coupang.com/#",
    "/404",
    "error",
]


def _is_dead(final_url: str, status: int) -> bool:
    if status == 404:
        return True
    url_lower = final_url.lower()
    # 정상: 상품 상세 페이지
    if "/vp/products/" in url_lower:
        return False
    # 단종: 홈 또는 에러 페이지
    for sig in DEAD_SIGNALS:
        if sig in url_lower:
            return True
    # 쿠팡 도메인이지만 상품 페이지가 아님 → 의심
    if "coupang.com" in url_lower:
        return True
    return False


def check_all():
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        reg = json.load(f)

    products = reg["products"]
    session = requests.Session()
    session.headers.update(HEADERS)

    results = {"ok": [], "dead": [], "error": []}

    total = sum(1 for v in products.values() if not v.get("removed"))
    print(f"\n쿠팡 링크 무결성 검증 ({total}개 상품)\n" + "=" * 60)

    for key, v in products.items():
        code = v.get("code", "?")
        name = v.get("name", "")[:35]

        if v.get("removed"):
            print(f"  [{code}] SKIP   {name}  (removed)")
            continue

        url = v.get("url") or key
        try:
            resp = session.get(url, timeout=10, allow_redirects=True)
            final = resp.url
            status = resp.status_code

            if _is_dead(final, status):
                tag = "DEAD "
                results["dead"].append((code, name, final))
            else:
                tag = "OK   "
                results["ok"].append((code, name))

            final_short = final[:70] if len(final) > 70 else final
            print(f"  [{code}] {tag} {name}")
            print(f"         → {final_short}  (HTTP {status})")
        except Exception as e:
            print(f"  [{code}] ERROR  {name}  ({e})")
            results["error"].append((code, name, str(e)))

        time.sleep(0.8)  # 쿠팡 봇 차단 방지

    # 요약
    print("\n" + "=" * 60)
    print(f"OK   : {len(results['ok'])}개")
    print(f"DEAD : {len(results['dead'])}개")
    print(f"ERROR: {len(results['error'])}개")

    if results["dead"]:
        print("\n단종 의심 상품:")
        for code, name, final in results["dead"]:
            print(f"  [{code}] {name}")
            print(f"         → {final[:70]}")

    if results["error"]:
        print("\n확인 불가 상품:")
        for code, name, err in results["error"]:
            print(f"  [{code}] {name}  ({err})")

    return results


if __name__ == "__main__":
    results = check_all()
    if results["dead"] or results["error"]:
        sys.exit(1)
