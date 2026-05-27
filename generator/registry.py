"""
상품 코드 레지스트리
- 포스팅할 상품마다 [001], [002]... 순번 부여
- 인포크링크(inpock.co.kr) 상품 목록과 코드 동기화 기준
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DATA_DIR

REGISTRY_PATH = os.path.join(DATA_DIR, "product_registry.json")


def _load() -> dict:
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"next_code": 1, "products": {}}


def _save(reg: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def assign_code(product_url: str, name: str = "", image_url: str = "") -> str:
    """
    상품 URL에 순번 코드 할당.
    이미 등록된 URL이면 기존 코드 반환 (중복 포스팅 방지).
    """
    reg = _load()
    key = (product_url or "")[:80]
    if key and key in reg["products"]:
        # image_url이 새로 들어왔으면 업데이트
        if image_url and not reg["products"][key].get("image_url"):
            reg["products"][key]["image_url"] = image_url
            _save(reg)
        return reg["products"][key]["code"]

    code = str(reg["next_code"]).zfill(3)
    if key:
        reg["products"][key] = {"code": code, "name": name, "url": product_url, "image_url": image_url}
    reg["next_code"] += 1
    _save(reg)
    return code


def get_all() -> list[dict]:
    """전체 등록 상품 목록 — 링크인바이오 페이지 생성용"""
    reg = _load()
    return [
        {
            "code": v["code"],
            "name": v.get("name", ""),
            "url": v.get("url", ""),
            "image_url": v.get("image_url", ""),
        }
        for v in reg["products"].values()
    ]
