"""
타 계정 게시글 자연스러운 댓글 달기 (노출 확대용)
- 키워드 검색 → 타계정 게시글 발견 → 게시글 페이지 직접 방문 → 본문 추출 → Groq 댓글 생성 → 포스팅
- 하루 최대 10개, 게시글 당 1회, 3~5분 간격 (자연스러운 패턴 유지)
"""
import asyncio
import json
import os
import sys
import logging
import random
import hashlib
from datetime import datetime, timedelta

from playwright.async_api import Page, BrowserContext

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import GROQ_API_KEY, THREADS_USERNAME, DATA_DIR

logger = logging.getLogger(__name__)

COMMENTED_PATH = os.path.join(DATA_DIR, "commented_posts.json")
THREADS_URL = "https://www.threads.com"

# 검색할 키워드 — 우리 계정 타겟층이 보는 게시글들
SEARCH_KEYWORDS = [
    "신기한생활용품",
    "신박한물건",
    "아이디어상품",
    "살림템추천",
    "주방꿀템",
    "생활꿀템",
    "반려동물장난감",
    "집꾸미기",
]

MAX_COMMENTS_PER_RUN = 10
MIN_DELAY_SEC = 180   # 댓글 사이 최소 3분
MAX_DELAY_SEC = 320   # 최대 약 5분

# 댓글 기록 보존 기간 (일)
HISTORY_DAYS = 30

# 너무 짧거나 범용적인 댓글 — 재생성 트리거
GENERIC_COMMENTS = {"오", "헐", "와", "오오", "ㄷㄷ", "대박", "좋다", "굳", "진짜"}


def _load_commented() -> set[str]:
    if not os.path.exists(COMMENTED_PATH):
        return set()
    with open(COMMENTED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cutoff = datetime.now() - timedelta(days=HISTORY_DAYS)
    recent = {k: v for k, v in data.items() if datetime.fromisoformat(v) > cutoff}
    return set(recent.keys())


def _save_commented(post_ids: dict[str, str]):
    os.makedirs(DATA_DIR, exist_ok=True)
    existing = {}
    if os.path.exists(COMMENTED_PATH):
        with open(COMMENTED_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    existing.update(post_ids)
    cutoff = datetime.now() - timedelta(days=HISTORY_DAYS)
    cleaned = {k: v for k, v in existing.items() if datetime.fromisoformat(v) > cutoff}
    with open(COMMENTED_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)


def _post_id_from_url(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def _extract_post_text(page: Page) -> str:
    """현재 게시글 페이지에서 본문 텍스트 추출"""
    await page.wait_for_timeout(1500)
    text = ""
    try:
        candidates = []
        els = await page.query_selector_all("div[dir='auto'], span[dir='auto']")
        for el in els:
            try:
                t = (await el.inner_text()).strip()
                # 너무 짧거나 UI 텍스트인 것 제외
                if len(t) >= 15 and not any(x in t for x in ["로그인", "가입하기", "Threads", "Meta", "계속하기"]):
                    candidates.append(t)
            except Exception:
                continue
        if candidates:
            text = max(candidates, key=len)
    except Exception as e:
        logger.warning(f"본문 추출 오류: {e}")
    return text[:500].strip()


def _generate_comment(post_text: str, retry: bool = False) -> str | None:
    """게시글 본문 기반 사람 같은 댓글 생성 (Groq)"""
    if not GROQ_API_KEY or not post_text.strip():
        return None
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        system = (
            "너는 Threads SNS를 즐겨 쓰는 평범한 한국인이야. "
            "생활용품·주방·살림 관련 게시글을 보고 진짜 사람처럼 자연스럽게 반응하는 댓글을 달아.\n\n"
            "반드시 지킬 규칙:\n"
            "- 반말, 친근하게\n"
            "- 게시글에서 언급된 구체적인 제품명·상황·특징을 댓글에 포함시킬 것\n"
            "- 최소 12자 이상, 최대 40자 이내\n"
            "- 이모지 0~1개\n"
            "- '오', '헐', '와' 같은 감탄사만으로 끝내지 말 것\n"
            "- 공감·경험 공유·구체적 질문·호기심 중 하나\n"
            "- 광고·홍보·링크·계정 언급 절대 금지\n\n"
            "좋은 댓글 예시 (이런 느낌으로):\n"
            "  · '계란 껍질 때문에 항상 애먹었는데 이거 써봐야겠다'\n"
            "  · '쌀 씻다가 흘린 게 한두 번이 아닌데 ㅋㅋ 나한테 딱이다'\n"
            "  · '실리콘랩 나도 쓰는데 밀봉력 진짜 좋더라'\n"
            "  · '이거 어디서 구매할 수 있어?'\n"
            "  · '다이소에 이런 게 있었어? 당장 가봐야겠다'\n\n"
            "댓글만 출력. 따옴표·설명 없이."
        )
        temperature = 0.9 if retry else 0.85
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"다음 게시글에 댓글 1개 작성:\n\n{post_text[:400]}"},
            ],
            max_tokens=80,
            temperature=temperature,
        )
        comment = resp.choices[0].message.content.strip().strip('"\'""''')
        return comment if comment else None
    except Exception as e:
        logger.warning(f"댓글 생성 실패: {e}")
        return None


def _is_quality_comment(comment: str) -> bool:
    """댓글 품질 판단 — 너무 짧거나 범용적이면 False"""
    if not comment or len(comment) < 12:
        return False
    # 감탄사만 있는지 확인
    stripped = comment.strip("!?ㅋㅎ ~. ")
    if stripped in GENERIC_COMMENTS:
        return False
    return True


async def _search_posts(page: Page, keyword: str, max_posts: int = 5) -> list[str]:
    """키워드 검색 후 타계정 게시글 URL 목록만 반환"""
    urls = []
    try:
        await page.goto(
            f"{THREADS_URL}/search?q={keyword}&serp_type=default",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        await page.wait_for_timeout(3000)

        links = await page.query_selector_all("a[href*='/post/']")
        seen_urls = set()

        for link in links:
            if len(urls) >= max_posts:
                break
            try:
                href = await link.get_attribute("href")
                if not href or href in seen_urls:
                    continue
                if f"/@{THREADS_USERNAME}/" in href:
                    continue
                seen_urls.add(href)
                full_url = f"{THREADS_URL}{href}" if href.startswith("/") else href
                urls.append(full_url)
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"검색 실패 ({keyword}): {e}")

    return urls


async def _visit_and_comment(page: Page, post_url: str) -> tuple[bool, str]:
    """
    게시글 직접 방문 → 본문 추출 → 댓글 생성 → 게시
    반환: (성공 여부, 댓글 텍스트)
    """
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(2000)

        # 본문 추출
        post_text = await _extract_post_text(page)
        if not post_text:
            logger.warning(f"본문 없음: {post_url[-35:]}")
            return False, ""

        logger.debug(f"추출 본문: {post_text[:80]}...")

        # 댓글 생성 (품질 미달 시 1회 재시도)
        comment = _generate_comment(post_text)
        if comment and not _is_quality_comment(comment):
            logger.info(f"  품질 미달 재생성: '{comment}'")
            comment = _generate_comment(post_text, retry=True)
        if not comment:
            return False, ""

        # 댓글 입력창
        reply_el = await page.query_selector("div[role='textbox']")
        if not reply_el:
            reply_el = await page.query_selector("[contenteditable='true']")
        if not reply_el:
            logger.warning(f"댓글창 없음: {post_url}")
            return False, ""

        await reply_el.click()
        await page.wait_for_timeout(600)
        await page.keyboard.type(comment, delay=50)
        await page.wait_for_timeout(800)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

        logger.info(f"댓글 완료: {comment} → {post_url[-35:]}")
        return True, comment

    except Exception as e:
        logger.warning(f"댓글 실패 ({post_url[-30:]}): {e}")
        return False, ""


async def run_engagement_session(max_comments: int = MAX_COMMENTS_PER_RUN):
    """독립 브라우저 세션으로 댓글 활동 실행 (main.py에서 직접 호출용)"""
    from playwright.async_api import async_playwright
    import json as _json

    cookie_path = os.path.join(os.path.dirname(__file__), "..", "data", "threads_cookies.json")
    if not os.path.exists(cookie_path):
        logger.warning("쿠키 파일 없음 — 댓글 활동 건너뜀")
        return

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
            with open(cookie_path) as f:
                cookies = _json.load(f)
            await context.add_cookies(cookies)

            page = await context.new_page()
            await page.goto("https://www.threads.com", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            if "login" in page.url:
                logger.warning("세션 만료 — 댓글 활동 건너뜀")
                return

            await run_engagement(page, max_comments)
        finally:
            await browser.close()


async def run_engagement(page: Page, max_comments: int = MAX_COMMENTS_PER_RUN):
    """키워드 검색 → 타계정 게시글 직접 방문 → 본문 읽고 자연스러운 댓글"""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY 미설정 — 댓글 기능 건너뜀")
        return

    commented_ids = _load_commented()
    new_commented: dict[str, str] = {}
    count = 0

    keywords = random.sample(SEARCH_KEYWORDS, min(len(SEARCH_KEYWORDS), 4))

    for keyword in keywords:
        if count >= max_comments:
            break

        logger.info(f"[댓글] 검색: '{keyword}'")
        post_urls = await _search_posts(page, keyword, max_posts=4)

        for post_url in post_urls:
            if count >= max_comments:
                break

            post_id = _post_id_from_url(post_url)
            if post_id in commented_ids:
                continue

            success, comment = await _visit_and_comment(page, post_url)
            if success:
                new_commented[post_id] = datetime.now().isoformat()
                commented_ids.add(post_id)
                count += 1

                if count < max_comments:
                    delay = random.randint(MIN_DELAY_SEC, MAX_DELAY_SEC)
                    logger.info(f"  다음 댓글까지 {delay}초 대기...")
                    await asyncio.sleep(delay)

    if new_commented:
        _save_commented(new_commented)

    logger.info(f"[댓글] 완료: {count}개")
