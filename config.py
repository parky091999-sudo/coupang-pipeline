from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
THREADS_USERNAME = os.getenv("THREADS_USERNAME")
THREADS_PASSWORD = os.getenv("THREADS_PASSWORD")

# 네이버 개발자센터 - 검색 API (쇼핑)
# https://developers.naver.com/apps → 애플리케이션 등록 → 검색 API 선택
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# 스케줄 시간 (24시간 기준)
SCHEDULE_TIMES = ["09:00", "13:00", "19:00"]

# 한 번 실행 시 포스팅할 최대 상품 수
MAX_PRODUCTS_PER_RUN = 3

# 쿠팡 스크래핑 대상 URL
COUPANG_URLS = {
    "rocket_deals": "https://www.coupang.com/np/campaigns/82",   # 로켓배송 특가
    "homepage": "https://www.coupang.com",                        # 메인 홈
}

# 데이터 저장 경로
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
