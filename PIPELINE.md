# 꿀픽 파이프라인 운영 문서

> 집 PC / 직장 PC / 핸드폰 어디서든 이 파일을 읽고 Claude에게 붙여넣으면 작업 맥락 공유 가능

---

## 시스템 개요

```
YouTube 트렌딩 영상
    ↓  Groq AI → 상품명 추출
네이버 쇼핑 API → 쿠팡 상품 매칭
    ↓
별점 4.5+ / 리뷰 100+ 필터 (Playwright)
    ↓
Groq AI → 쓰레드 포스팅 텍스트 생성
    ↓
Threads 자동 포스팅 (Playwright)
    ↓
docs/index.html  (상품 페이지)  ← GitHub Pages 공개
docs/feed.html   (피드 페이지)  ← GitHub Pages 공개
```

**실행 주기:** 매일 09:00 KST (GitHub Actions 자동)  
**1회 수집:** 상품 3개 → Threads 게시글 3개 → 페이지 업데이트

---

## 페이지 URL

| 페이지 | 경로 | 설명 |
|--------|------|------|
| 상품 목록 | `docs/index.html` | 전체 등록 상품 카드 |
| 피드 기록 | `docs/feed.html`  | 게시된/생성된 포스팅 |

GitHub Pages 활성화 후: `https://<계정>.github.io/<저장소명>/`

---

## 파일 구조

```
coupang_pipeline/
├── main.py                  ← 파이프라인 진입점 (python main.py)
├── config.py                ← 설정 상수 (품질 필터, 스케줄 등)
├── generate_page.py         ← 상품 페이지 생성 (docs/index.html)
├── generate_feed_page.py    ← 피드 페이지 생성 (docs/feed.html)
├── preview.py               ← 로컬 드라이런 (브라우저 미리보기)
├── scraper/
│   ├── naver_shopping.py    ← 네이버 쇼핑 API 스크래퍼
│   └── youtube_trending.py  ← YouTube 트렌딩 → 상품 탐지
├── generator/
│   ├── content.py           ← Groq AI 게시글 생성
│   └── registry.py          ← 상품 코드 레지스트리 관리
├── poster/
│   ├── threads.py           ← Threads 자동 포스터
│   └── threads_login.py     ← 쿠키 저장 (최초 1회)
├── data/
│   ├── product_registry.json ← 등록 상품 목록 + 차단 목록 (git 추적)
│   ├── feed_posts.json       ← 포스팅 기록 (git 추적)
│   └── posted_ids.json       ← 중복 포스팅 방지 (git 추적)
├── docs/
│   ├── index.html            ← 상품 페이지 (GitHub Pages)
│   └── feed.html             ← 피드 페이지 (GitHub Pages)
├── .github/workflows/
│   └── daily.yml             ← GitHub Actions 자동화
└── PIPELINE.md               ← 이 파일
```

---

## 환경 변수 (.env)

```env
ANTHROPIC_API_KEY=sk-ant-...          # Claude AI (콘텐츠 생성)
GROQ_API_KEY=gsk_...                  # Groq AI (무료, 상품명추출+게시글)
NAVER_CLIENT_ID=...                   # 네이버 개발자센터 앱 ID
NAVER_CLIENT_SECRET=...               # 네이버 앱 시크릿
YOUTUBE_API_KEY=AIza...               # YouTube Data API v3
THREADS_USERNAME=@아이디              # Threads 계정
THREADS_PASSWORD=비밀번호             # Threads 비밀번호
```

---

## GitHub 초기 설정 (최초 1회)

```bash
# 1. 저장소 초기화
cd C:\박관용\CLAUDE\ai-agent\coupang_pipeline
git init
git add .
git commit -m "init: 꿀픽 파이프라인"

# 2. GitHub에 새 저장소 만들고 (Public 권장 - Pages 무료)
git remote add origin git@github.com:<계정>/<저장소명>.git
git push -u origin main

# 3. GitHub Pages 설정
# Settings → Pages → Source: Deploy from a branch
# Branch: main, Folder: /docs → Save

# 4. Actions 권한 설정
# Settings → Actions → General → Workflow permissions
# → "Read and write permissions" 선택 → Save
```

### GitHub Secrets 등록

Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|------------|-----|
| `ANTHROPIC_API_KEY` | .env의 값 |
| `GROQ_API_KEY` | .env의 값 |
| `NAVER_CLIENT_ID` | .env의 값 |
| `NAVER_CLIENT_SECRET` | .env의 값 |
| `YOUTUBE_API_KEY` | .env의 값 |
| `THREADS_USERNAME` | Threads 아이디 |
| `THREADS_PASSWORD` | Threads 비밀번호 |
| `THREADS_COOKIES_B64` | 쿠키 base64 (선택, 아래 참조) |

### Threads 쿠키 등록 (선택)

로컬에서 먼저 로그인하면 Actions에서도 세션 유지 가능:

```bash
# 로컬에서 쿠키 저장
python poster/threads_login.py

# base64 인코딩 후 Secret에 등록
python -c "import base64,open; print(base64.b64encode(open('data/threads_cookies.json','rb').read()).decode())"
```

위 출력값을 `THREADS_COOKIES_B64` Secret으로 등록.  
쿠키가 만료되면 로컬에서 재실행 후 재등록 필요.

---

## 수동 조작 방법

### 상품 페이지만 바로 갱신

```bash
python generate_page.py
python generate_feed_page.py
```

### 드라이런 미리보기 (실제 포스팅 없이 확인)

```bash
python preview.py
```
→ 브라우저 자동 오픈, 상품 카드 + 쓰레드 피드 미리보기

### 한 번만 실행 (포스팅 포함)

```bash
python main.py
```

### 스케줄 모드 (로컬에서 계속 실행)

```bash
python main.py --schedule
```

---

## 상품 관리

### 상품 차단 (중국산 등 재진입 방지)

`data/product_registry.json` 의 `blocked_item_ids` 배열에 itemId 추가:

```json
{
  "blocked_item_ids": ["28158261236", "26870958522", "25050336169"],
  ...
}
```

쿠팡 상품 URL에서 itemId 확인: `...&itemId=28158261236&...`

### 상품 수동 삭제

`data/product_registry.json` 의 `products` 객체에서 해당 항목 삭제 후:
```bash
python generate_page.py
```

### 상품 검색 키워드 변경

`scraper/naver_shopping.py` 의 `SEARCH_KEYWORDS` 리스트 수정

### 품질 필터 설정 변경

`config.py`:
```python
CHECK_RATING      = True   # 별점/리뷰수 체크 (Playwright, 느림)
MIN_REVIEW_COUNT  = 100    # 최소 리뷰수
MIN_RATING        = 4.5    # 최소 별점
```

---

## 쿠팡파트너스 수익화 전환

`config.py`:
```python
COUPANG_PARTNERS_ACTIVE = False  # → True 로 변경
```

True로 바꾸면:
- 모든 포스팅 앞에 `[광고]` 자동 추가
- 공정위 고지문 자동 포함

---

## 자주 있는 상황별 대처

### GitHub Actions 실패 시
1. Actions 탭 → 실패한 워크플로 → 로그 확인
2. API 키 만료/오류가 대부분 → Secrets 재확인
3. 수동 실행: Actions → Daily Pipeline → Run workflow

### 상품이 계속 0개 수집될 때
1. 네이버 API 쿼터 확인 (25,000건/일)
2. YouTube API 쿼터 확인 (10,000 units/일)
3. `preview.py` 로 로컬 테스트

### Threads 포스팅이 안 될 때
1. 쿠키 만료 → `python poster/threads_login.py` 재실행
2. THREADS_COOKIES_B64 Secret 재등록
3. 계정 정지 여부 확인

### 페이지가 GitHub Pages에 안 보일 때
1. Settings → Pages에서 배포 상태 확인
2. `docs/index.html` 파일이 repo에 있는지 확인
3. Actions 워크플로가 성공적으로 push했는지 확인

---

## 다른 기기에서 작업 이어가기

```bash
# 직장 PC / 핸드폰(Termux) 등 어디서든
git clone git@github.com:<계정>/<저장소명>.git
cd <저장소명>
cp .env.example .env   # 환경변수 직접 입력 필요
pip install -r requirements.txt
playwright install chromium
```

Claude Code에서 이 PIPELINE.md를 먼저 읽히면 전체 맥락 공유 완료.
