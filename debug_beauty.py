"""
쿠팡 뷰티 카테고리 DOM 구조 조사
실행: python debug_beauty.py
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 뷰티 카테고리 할인율 높은 순
BEAUTY_URL = "https://www.coupang.com/np/categories/194?sorter=discountRateDesc"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)  # 봇 탐지 우회

        print("[1] 쿠팡 홈 접속...")
        await page.goto("https://www.coupang.com", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(DATA_DIR, "beauty_00_home.png"))

        # 팝업 닫기 시도
        for close_sel in ["button.close", ".modal-close", "[aria-label='닫기']", ".coupang-modal button"]:
            el = await page.query_selector(close_sel)
            if el:
                await el.click()
                await page.wait_for_timeout(500)
                break
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # 검색창에 뷰티 검색
        print("[2] 검색창에 '뷰티' 입력...")
        search = await page.query_selector("input#headerSearchInput, input[name='q'], input[type='search']")
        if search:
            await search.click()
            await page.wait_for_timeout(300)
            await page.keyboard.type("뷰티", delay=80)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(4000)

        print(f"  검색 후 URL: {page.url}")
        await page.screenshot(path=os.path.join(DATA_DIR, "beauty_01_page.png"))
        print("  스크린샷: beauty_01_page.png")

        # 할인율 높은 순 정렬
        print("[3] 할인율 정렬 탐색...")
        sort_selectors = [
            "a:has-text('할인율')",
            "button:has-text('할인율')",
            "[data-sorter='discountRateDesc']",
            "a[href*='discountRateDesc']",
            "li:has-text('할인율') a",
        ]
        for sel in sort_selectors:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(3000)
                print(f"  할인율 정렬 클릭: {sel}")
                break
        else:
            print("  할인율 정렬 버튼 없음 - 현재 상태로 진행")

        print(f"  정렬 후 URL: {page.url}")
        await page.screenshot(path=os.path.join(DATA_DIR, "beauty_01b_sorted.png"))
        print("  스크린샷: beauty_01b_sorted.png")

        # 상품 카드 셀렉터 탐색
        print("\n[2] 상품 카드 셀렉터 탐색...")
        candidates = [
            "li.search-product",
            "li[class*='search-product']",
            "li[class*='product-item']",
            ".product-list li",
            "ul.product-list > li",
            "[data-item-id]",
            "article[class*='product']",
        ]
        found_selector = None
        for sel in candidates:
            els = await page.query_selector_all(sel)
            print(f"  {sel}: {len(els)}개")
            if els and not found_selector:
                found_selector = sel

        if not found_selector:
            print("  상품 카드를 찾지 못했습니다. HTML 일부 저장...")
            html = await page.content()
            with open(os.path.join(DATA_DIR, "beauty_page.html"), "w", encoding="utf-8") as f:
                f.write(html[:50000])
            print("  beauty_page.html 저장 완료 (앞 50000자)")
            await browser.close()
            return

        print(f"\n[3] 첫 번째 상품 카드 상세 분석 (셀렉터: {found_selector})...")
        cards = await page.query_selector_all(found_selector)
        card = cards[0]

        # 내부 셀렉터 후보들
        sub_selectors = {
            "상품명": [".name", ".item-name", "div.name", "a.product-name", ".search-item-name", "span.name"],
            "할인가": ["em.price-value", ".price-value", ".sale-price", "strong.price", ".final-price"],
            "원가": ["del.base-price", ".base-price", "del", ".original-price", ".before-price"],
            "할인율": ["span.percent", ".discount-rate", "[class*='percent']", ".badge-discount", "em.percent"],
            "리뷰수": [".rating-total-count", ".count", "[class*='count']", ".review-count", "em.rating-total-count"],
            "평점": ["em.rating", ".rating", "[class*='rating']", "span.rating"],
            "이미지": ["img.search-product-wrap-img", ".thumbnail img", "img[src*='thumbnail']", "img"],
            "링크": ["a[href*='/vp/products/']", "a.search-product-link", "a"],
        }

        results = {}
        for field, sels in sub_selectors.items():
            for sel in sels:
                el = await card.query_selector(sel)
                if el:
                    try:
                        text = (await el.inner_text()).strip()
                        attr = await el.get_attribute("src") or await el.get_attribute("href") or ""
                        results[field] = {"selector": sel, "value": text or attr}
                        break
                    except Exception:
                        continue
            if field not in results:
                results[field] = {"selector": None, "value": "NOT FOUND"}

        print("\n  발견된 필드:")
        for field, info in results.items():
            print(f"    {field}: [{info['selector']}] = '{str(info['value'])[:60]}'")

        # 처음 5개 상품 샘플 출력
        print(f"\n[4] 상위 5개 상품 샘플...")
        name_sel = results.get("상품명", {}).get("selector")
        price_sel = results.get("할인가", {}).get("selector")
        rate_sel = results.get("할인율", {}).get("selector")
        review_sel = results.get("리뷰수", {}).get("selector")

        for i, card in enumerate(cards[:5]):
            try:
                name = ""
                price = ""
                rate = ""
                reviews = ""
                if name_sel:
                    el = await card.query_selector(name_sel)
                    if el: name = (await el.inner_text()).strip()[:50]
                if price_sel:
                    el = await card.query_selector(price_sel)
                    if el: price = (await el.inner_text()).strip()
                if rate_sel:
                    el = await card.query_selector(rate_sel)
                    if el: rate = (await el.inner_text()).strip()
                if review_sel:
                    el = await card.query_selector(review_sel)
                    if el: reviews = (await el.inner_text()).strip()
                print(f"  [{i+1}] {rate} | {price} | 리뷰{reviews} | {name}")
            except Exception as e:
                print(f"  [{i+1}] 파싱 오류: {e}")

        # 결과 저장
        with open(os.path.join(DATA_DIR, "beauty_selectors.json"), "w", encoding="utf-8") as f:
            json.dump({"card_selector": found_selector, "fields": results}, f, ensure_ascii=False, indent=2)
        print("\n  셀렉터 결과 저장: beauty_selectors.json")

        await page.screenshot(path=os.path.join(DATA_DIR, "beauty_02_done.png"))
        await browser.close()
        print("\n[완료]")


if __name__ == "__main__":
    asyncio.run(debug())
