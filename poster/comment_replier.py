"""
쓰레드 댓글 자동 감지 및 대댓글
- 최근 7일 story 게시글의 댓글 감지
- Groq API로 자연스러운 대댓글 생성 후 포스팅
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from hashlib import md5

from playwright.async_api import Page, async_playwright, BrowserContext

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import THREADS_USERNAME, DATA_DIR
from generator.reply import generate_reply

logger = logging.getLogger(__name__)

RECENT_POSTS_PATH = os.path.join(DATA_DIR, "recent_posts.json")
REPLIED_PATH = os.path.join(DATA_DIR, "replied_comments.json")
COOKIE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "threads_cookies.json")
THREADS_URL = "https://www.threads.com"


# ── 데이터 I/O ────────────────────────────────────────────────────────────────

def load_recent_posts() -> list[dict]:
    if not os.path.exists(RECENT_POSTS_PATH):
        return []
    with open(RECENT_POSTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_recent_posts(posts: list[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RECENT_POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def add_recent_post(post_url: str, post_type: str = "story"):
    """story 게시글 URL 등록 (댓글 감지 대상)"""
    if not post_url or "/post/" not in post_url:
        return
    posts = load_recent_posts()
    if any(p["url"] == post_url for p in posts):
        return
    posts.append({
        "url": post_url,
        "posted_at": datetime.now().isoformat(),
        "post_type": post_type,
    })
    # 7일 지난 것 제거
    cutoff = datetime.now() - timedelta(days=7)
    posts = [p for p in posts if datetime.fromisoformat(p["posted_at"]) > cutoff]
    save_recent_posts(posts)
    logger.info(f"최근 포스트 등록: {post_url}")


def load_replied() -> dict:
    if not os.path.exists(REPLIED_PATH):
        return {}
    with open(REPLIED_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_replied(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPLIED_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _comment_key(username: str, text: str) -> str:
    return md5(f"{username}:{text[:80]}".encode()).hexdigest()[:12]


# ── Playwright 로직 ───────────────────────────────────────────────────────────

async def _login(context: BrowserContext) -> Page:
    import json as _json
    with open(COOKIE_PATH) as f:
        cookies = _json.load(f)
    await context.add_cookies(cookies)
    page = await context.new_page()
    await page.goto(THREADS_URL, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)
    if "login" in page.url:
        raise RuntimeError("세션 만료 — threads_login.py 재실행 필요")
    return page


async def get_comments(page: Page, post_url: str) -> list[dict]:
    """포스트에서 타 유저 댓글 추출"""
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4000)

        comments = await page.evaluate(f"""
            () => {{
                const myUser = '{THREADS_USERNAME}';
                const results = [];
                const seen = new Set();

                // time 요소 기준으로 댓글 블록 탐색
                document.querySelectorAll('time').forEach(time => {{
                    const block = time.closest('[role="article"]')
                                || time.closest('article')
                                || time.parentElement?.parentElement;
                    if (!block) return;

                    const userLink = block.querySelector('a[href^="/@"]');
                    if (!userLink) return;
                    const username = userLink.getAttribute('href').replace('/@', '').split('/')[0];
                    if (!username || username === myUser) return;

                    const textEls = block.querySelectorAll('div[dir="auto"]');
                    let text = '';
                    textEls.forEach(el => {{
                        const t = el.innerText?.trim();
                        if (t && t.length > 2) text = t;
                    }});

                    if (!text) return;
                    const key = username + ':' + text.slice(0, 40);
                    if (seen.has(key)) return;
                    seen.add(key);
                    results.push({{ username, text }});
                }});

                return results;
            }}
        """)
        return comments or []
    except Exception as e:
        logger.warning(f"댓글 추출 실패 ({post_url}): {e}")
        return []


async def post_reply(page: Page, post_url: str, reply_text: str) -> bool:
    """포스트 최상위 답글 달기"""
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        reply_el = await page.query_selector("div[role='textbox']")
        if not reply_el:
            reply_el = await page.query_selector("[contenteditable='true']")
        if not reply_el:
            logger.warning("답글 입력창 없음")
            return False

        await reply_el.click()
        await page.wait_for_timeout(500)

        lines = reply_text.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=30)
            if i < len(lines) - 1:
                await page.keyboard.press("Shift+Enter")
                await page.wait_for_timeout(100)

        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3000)
        logger.info(f"대댓글 완료: {reply_text[:30]}")
        return True
    except Exception as e:
        logger.error(f"대댓글 포스팅 실패: {e}")
        return False


# ── 메인 실행 ─────────────────────────────────────────────────────────────────

async def run_comment_replies(page: Page):
    """최근 story 게시글 댓글 감지 → 자동 대댓글"""
    posts = load_recent_posts()
    story_posts = [p for p in posts if p.get("post_type") == "story"]

    if not story_posts:
        logger.info("댓글 확인할 포스트 없음")
        return

    replied = load_replied()
    reply_count = 0
    logger.info(f"댓글 확인 시작: {len(story_posts)}개 포스트")

    for post in story_posts:
        url = post["url"]
        try:
            comments = await get_comments(page, url)
            if not comments:
                continue

            post_replied = set(replied.get(url, []))
            new_comments = [
                c for c in comments
                if _comment_key(c["username"], c["text"]) not in post_replied
            ]

            if not new_comments:
                logger.info(f"새 댓글 없음: {url[-30:]}")
                continue

            logger.info(f"새 댓글 {len(new_comments)}개: {url[-30:]}")

            # 여러 댓글을 하나의 맥락으로 묶어 대댓글 1개 생성
            combined = "\n".join([
                f"@{c['username']}: {c['text']}" for c in new_comments[:3]
            ])
            reply_text = generate_reply(combined)
            if not reply_text:
                continue

            success = await post_reply(page, url, reply_text)
            if success:
                for c in new_comments:
                    post_replied.add(_comment_key(c["username"], c["text"]))
                replied[url] = list(post_replied)
                save_replied(replied)
                reply_count += 1
                await asyncio.sleep(15)

        except Exception as e:
            logger.error(f"댓글 처리 오류 ({url}): {e}")

    logger.info(f"대댓글 완료: {reply_count}개")


async def check_and_reply_comments():
    """독립 브라우저 세션으로 댓글 대댓글 실행"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        try:
            page = await _login(context)
            await run_comment_replies(page)
        finally:
            await browser.close()
