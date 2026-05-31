"""
쓰레드 UI 셀렉터 디버그 스크립트
실행: python debug_threads.py
- 브라우저를 열고 쿠키로 로그인
- 글쓰기 화면까지 이동하면서 각 단계 스크린샷 저장
- 어떤 요소가 실제로 있는지 출력
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIE_PATH = os.path.join(os.path.dirname(__file__), "data", "threads_cookies.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
THREADS_URL = "https://www.threads.com"


async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )

        # 쿠키 로드
        with open(COOKIE_PATH) as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print(f"[OK] 쿠키 로드: {len(cookies)}개")

        page = await context.new_page()

        # 1단계: 홈 접속
        print("\n[1] 쓰레드 홈 접속 중...")
        await page.goto(THREADS_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"  현재 URL: {page.url}")
        await page.screenshot(path=os.path.join(DATA_DIR, "debug_01_home.png"))
        print("  스크린샷 저장: debug_01_home.png")

        if "login" in page.url:
            print("  [ERROR] 세션 만료 - threads_login.py 재실행 필요")
            await browser.close()
            return

        # 2단계: intent/post URL 시도
        print("\n[2] /intent/post 접속 중...")
        await page.goto(f"{THREADS_URL}/intent/post", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        print(f"  현재 URL: {page.url}")
        await page.screenshot(path=os.path.join(DATA_DIR, "debug_02_intent_post.png"))
        print("  스크린샷 저장: debug_02_intent_post.png")

        # 3단계: 텍스트 입력 영역 탐색
        print("\n[3] 텍스트 입력 영역 탐색...")
        text_selectors = [
            "[contenteditable='true']",
            "div[role='textbox']",
            "textarea",
            "[data-lexical-editor]",
            "p[data-contents]",
            "div[contenteditable]",
        ]
        for sel in text_selectors:
            els = await page.query_selector_all(sel)
            if els:
                print(f"  [FOUND] {sel} → {len(els)}개 발견")
                for i, el in enumerate(els[:3]):
                    try:
                        text = await el.inner_text()
                        placeholder = await el.get_attribute("placeholder") or ""
                        aria = await el.get_attribute("aria-label") or ""
                        print(f"    [{i}] text='{text[:30]}' placeholder='{placeholder}' aria='{aria}'")
                    except Exception:
                        pass
            else:
                print(f"  [MISS]  {sel}")

        # 4단계: 버튼 탐색
        print("\n[4] 버튼 탐색...")
        all_buttons = await page.query_selector_all("button, div[role='button']")
        print(f"  총 버튼 수: {len(all_buttons)}개")
        for btn in all_buttons:
            try:
                text = (await btn.inner_text()).strip()
                aria = await btn.get_attribute("aria-label") or ""
                if text or aria:
                    print(f"  버튼: text='{text[:40]}' aria='{aria[:40]}'")
            except Exception:
                pass

        # 5단계: 텍스트 입력 시도
        print("\n[5] 텍스트 입력 시도...")
        typed = False
        for sel in ["[contenteditable='true']", "div[role='textbox']", "div[contenteditable]"]:
            el = await page.query_selector(sel)
            if el:
                try:
                    await el.click()
                    await page.wait_for_timeout(500)
                    await page.keyboard.type("테스트 디버그", delay=80)
                    await page.wait_for_timeout(1000)
                    await page.screenshot(path=os.path.join(DATA_DIR, "debug_03_typed.png"))
                    print(f"  [OK] '{sel}'에 입력 완료 → debug_03_typed.png")
                    typed = True
                    break
                except Exception as e:
                    print(f"  [FAIL] {sel}: {e}")

        if not typed:
            print("  [ERROR] 텍스트 입력 가능한 요소 없음")

        # 6단계: 게시 버튼 클릭 (수정된 방식)
        print("\n[6] 게시 버튼 클릭 시도 (get_by_role + exact + last)...")
        await page.wait_for_timeout(1000)
        clicked = False
        try:
            post_btn = page.get_by_role("button", name="게시", exact=True)
            count = await post_btn.count()
            print(f"  '게시' 버튼 총 {count}개 발견")
            if count > 0:
                await post_btn.last.click()
                clicked = True
                print("  [OK] 마지막 '게시' 버튼 클릭!")
        except Exception as e:
            print(f"  [FAIL] {e}")

        await page.wait_for_timeout(4000)
        await page.screenshot(path=os.path.join(DATA_DIR, "debug_04_after_post.png"))
        print(f"  클릭 후 URL: {page.url}")
        print("  스크린샷: debug_04_after_post.png")

        if clicked:
            print("\n  ★ 포스팅 성공 여부는 쓰레드 계정에서 확인하세요")
        else:
            print("\n  ✗ 버튼 클릭 실패")

        print("\n[완료] 브라우저 5초 후 종료")
        await page.wait_for_timeout(5000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug())
