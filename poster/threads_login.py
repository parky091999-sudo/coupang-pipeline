"""
쓰레드 수동 로그인 → 쿠키 저장 스크립트
처음 1번만 실행하면 이후 자동 로그인 불필요
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "threads_cookies.json")

async def manual_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        page = await context.new_page()

        print("브라우저가 열립니다. 직접 로그인해주세요.")
        print("로그인 완료 후 메인 피드가 보이면 Enter를 누르세요.")

        await page.goto("https://www.threads.com/login")

        # 사용자가 직접 로그인할 때까지 대기
        input("\n로그인 완료 후 Enter 누르세요...")

        # 쿠키 저장
        cookies = await context.cookies()
        os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
        with open(COOKIE_PATH, "w") as f:
            json.dump(cookies, f)

        print(f"쿠키 저장 완료: {COOKIE_PATH}")
        print(f"저장된 쿠키: {len(cookies)}개")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(manual_login())
