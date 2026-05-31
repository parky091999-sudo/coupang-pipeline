"""
쿠팡 DOM 구조 확인용 디버그 스크립트 v2
- 실제 브라우저로 열어서 스크롤 후 셀렉터 확인
"""
import asyncio
from playwright.async_api import async_playwright
import os

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="ko-KR",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        print("쿠팡 접속 중... (브라우저 창 확인하세요)")
        await page.goto("https://www.coupang.com", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)  # JS 렌더링 대기
        await page.wait_for_timeout(3000)

        # 스크롤해서 lazy load 트리거
        print("스크롤 중...")
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(800)

        await page.wait_for_timeout(2000)

        # 스크린샷
        os.makedirs("data", exist_ok=True)
        await page.screenshot(path="data/after_scroll.png")
        print("스크린샷 저장: data/after_scroll.png")

        # 셀렉터 전수 확인
        print("\n=== 셀렉터 결과 ===")
        selectors = [
            "li.promotion-carousel-item",
            "a.impression-logged",
            ".item-title",
            ".sales-price",
            ".discount-rate",
            "[class*='product-card']",
            "[class*='ProductCard']",
            "[class*='deal']",
            "li[data-id]",
            ".baby-product",
        ]
        for sel in selectors:
            count = await page.eval_on_selector_all(sel, "els => els.length")
            if count > 0:
                print(f"  ✅ {sel}: {count}개")
            else:
                print(f"  ❌ {sel}: 0개")

        # 현재 페이지 HTML 저장
        html = await page.content()
        with open("data/after_scroll.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\nHTML 저장 완료: {len(html):,} bytes")

        # 첫 번째 li 클래스 샘플 출력
        first_li = await page.query_selector("li")
        if first_li:
            cls = await first_li.get_attribute("class")
            print(f"\n첫 번째 li 클래스: {cls}")

        print("\n10초 후 종료됩니다. 브라우저를 직접 확인하세요.")
        await page.wait_for_timeout(10000)
        await browser.close()

asyncio.run(debug())
