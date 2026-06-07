"""
쿠팡 스크래퍼
- 쿠팡 홈페이지 프로모션 섹션에서 할인 상품 수집
- 실제 DOM 구조 기반 셀렉터 사용
"""
import asyncio
import json
import os
import re
import sys
import logging
from datetime import datetime
from playwright.async_api import async_playwright, Page

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import DATA_DIR, MAX_PRODUCTS_PER_RUN

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def scrape_homepage_deals(max_items: int = MAX_PRODUCTS_PER_RUN) -> list[dict]:
    """쿠팡 홈페이지 프로모션 상품 스크래핑"""
    products = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await page.set_extra_http_headers({"Accept-Language": "ko-KR,ko;q=0.9"})

        try:
            logger.info("쿠팡 홈페이지 접속 중...")
            await page.goto("https://www.coupang.com", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            # 스크롤해서 JS 렌더링 트리거
            logger.info("페이지 스크롤 중...")
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 600)")
                await page.wait_for_timeout(600)
            await page.wait_for_timeout(1500)

            # 프로모션 캐러셀 상품 수집
            products = await _scrape_promotion_items(page, max_items)

            # 부족하면 오늘의 발견(개인화) 섹션에서 추가
            if len(products) < max_items:
                extra = await _scrape_personalized_items(page, max_items - len(products))
                products.extend(extra)

        except Exception as e:
            logger.error(f"스크래핑 오류: {e}")
        finally:
            await browser.close()

    logger.info(f"최종 수집 상품: {len(products)}개")
    return products


async def _scrape_promotion_items(page: Page, max_items: int) -> list[dict]:
    """프로모션 캐러셀 섹션 스크래핑 (할인율, 가격 있는 상품)"""
    products = []
    try:
        cards = await page.query_selector_all("li.promotion-carousel-item")
        logger.info(f"프로모션 카드: {len(cards)}개 발견")

        for card in cards:
            try:
                product = await _parse_promotion_card(card)
                if product:
                    products.append(product)
                    if len(products) >= max_items:
                        break
            except Exception as e:
                logger.debug(f"카드 파싱 실패: {e}")
    except Exception as e:
        logger.error(f"프로모션 섹션 오류: {e}")
    return products


async def _parse_promotion_card(card) -> dict | None:
    """프로모션 카드 파싱"""
    try:
        # 상품명
        name_el = await card.query_selector(".item-title")
        name = (await name_el.inner_text()).strip() if name_el else None
        if not name:
            return None

        # 할인율
        rate_el = await card.query_selector(".discount-rate")
        rate_text = (await rate_el.inner_text()).strip() if rate_el else "0"
        discount_rate = int(re.sub(r"[^\d]", "", rate_text) or "0")

        # 할인가
        price_el = await card.query_selector(".sales-price")
        price = (await price_el.inner_text()).strip() if price_el else ""

        # 원가
        orig_el = await card.query_selector(".origin-price")
        original_price = (await orig_el.inner_text()).strip() if orig_el else price

        # 이미지
        img_el = await card.query_selector(".promotion-item-image img, img")
        image_url = await img_el.get_attribute("src") if img_el else None
        if image_url and image_url.startswith("//"):
            image_url = "https:" + image_url

        # 링크
        link_el = await card.query_selector("a")
        href = await link_el.get_attribute("href") if link_el else None
        product_url = f"https://www.coupang.com{href}" if href and href.startswith("/") else href

        # 배지
        badge_el = await card.query_selector(".promotion-badge")
        badge = (await badge_el.inner_text()).strip() if badge_el else ""

        return {
            "name": name,
            "price": price,
            "original_price": original_price,
            "discount_rate": discount_rate,
            "image_url": image_url,
            "product_url": product_url,
            "badge": badge,
            "scraped_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.debug(f"파싱 오류: {e}")
        return None


async def _scrape_personalized_items(page: Page, max_items: int) -> list[dict]:
    """오늘의 발견 (개인화 추천) 섹션 스크래핑"""
    products = []
    try:
        cards = await page.query_selector_all("a.impression-logged")
        logger.info(f"개인화 카드: {len(cards)}개 발견")

        for card in cards:
            try:
                # item-image 있는 카드만
                img_div = await card.query_selector(".item-image")
                if not img_div:
                    continue

                name_el = await card.query_selector(".item-info-wrap span")
                name = (await name_el.inner_text()).strip() if name_el else None
                if not name:
                    continue

                # 빨간 할인 텍스트에서 % 추출
                rate_el = await card.query_selector("[class*='cb1400']")
                rate_text = (await rate_el.inner_text()).strip() if rate_el else ""
                rate_match = re.search(r"(\d+)", rate_text)
                discount_rate = int(rate_match.group(1)) if rate_match else 0

                img_el = await card.query_selector(".item-image img")
                image_url = await img_el.get_attribute("src") if img_el else None
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url

                href = await card.get_attribute("href")
                product_url = f"https://www.coupang.com{href}" if href and href.startswith("/") else href

                products.append({
                    "name": name,
                    "price": "",
                    "original_price": "",
                    "discount_rate": discount_rate,
                    "image_url": image_url,
                    "product_url": product_url,
                    "badge": "",
                    "scraped_at": datetime.now().isoformat(),
                })

                if len(products) >= max_items:
                    break
            except Exception as e:
                logger.debug(f"개인화 카드 파싱 실패: {e}")
    except Exception as e:
        logger.error(f"개인화 섹션 오류: {e}")
    return products


def save_products(products: list[dict], filename: str = "products.json"):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    logger.info(f"저장 완료: {path}")
    return path


def load_products(filename: str = "products.json") -> list[dict]:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    products = await scrape_homepage_deals()
    if products:
        save_products(products)
        print(f"\n수집된 상품 {len(products)}개:")
        for p in products:
            print(f"  [{p['discount_rate']}%] {p['name'][:40]} - {p['price']}")
    else:
        print("수집된 상품이 없습니다.")


if __name__ == "__main__":
    asyncio.run(run())
