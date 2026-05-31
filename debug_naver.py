import requests
from dotenv import load_dotenv
import os

load_dotenv()

headers = {
    "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
    "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET"),
}
resp = requests.get(
    "https://openapi.naver.com/v1/search/shop.json",
    headers=headers,
    params={"query": "스킨케어 할인", "display": 5},
)
items = resp.json().get("items", [])
for item in items:
    lp = int(item.get("lprice") or 0)
    hp = int(item.get("hprice") or 0)
    disc = round((1 - lp / hp) * 100) if hp > lp > 0 else 0
    print(f"[{disc}%] mall={item['mallName'][:8]} | lp={lp:,} hp={hp:,} | {item['title'][:35]}")
