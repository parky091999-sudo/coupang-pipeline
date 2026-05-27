"""
링크인바이오 페이지 생성기
실행: python generate_page.py
출력: docs/index.html  → GitHub Pages 호스팅용
"""
import os
import sys

sys.path.append(os.path.dirname(__file__))
from generator.registry import get_all
from config import COUPANG_PARTNERS_ACTIVE

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "docs", "index.html")

_AD_DISCLOSURE = "이 페이지의 일부 링크는 쿠팡파트너스 활동의 일환으로, 구매 시 수수료를 받을 수 있습니다."


def build_cards(products: list[dict]) -> str:
    if not products:
        return '<p class="empty">아직 등록된 상품이 없습니다</p>'

    html = ""
    for p in sorted(products, key=lambda x: x["code"]):
        code = p["code"]
        name = p.get("name", "")
        url = p.get("url") or "#"
        img = p.get("image_url", "")

        img_tag = (
            f'<img src="{img}" alt="{name}" loading="lazy" '
            f'onerror="this.parentElement.classList.add(\'no-img\')">'
            if img else ""
        )
        target = 'target="_blank" rel="noopener noreferrer"' if url != "#" else ""

        html += f"""
    <div class="card" data-code="{code}" data-name="{name.lower()}">
      {img_tag}
      <div class="card-body">
        <span class="badge">[{code}]</span>
        <p class="name">{name}</p>
        <a href="{url}" {target} class="btn">쿠팡에서 보기 →</a>
      </div>
    </div>"""
    return html


def build_html(products: list[dict]) -> str:
    cards = build_cards(products)
    count = len(products)
    disclosure = (
        f'<p class="disclosure">{_AD_DISCLOSURE}</p>'
        if COUPANG_PARTNERS_ACTIVE else ""
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>꿀픽 | 보다가 이게 뭐야 싶은 것들</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans KR', sans-serif;
    background: #f7f7f7;
    color: #222;
    min-height: 100vh;
  }}
  header {{
    background: #fff;
    padding: 18px 16px 12px;
    text-align: center;
    border-bottom: 1px solid #efefef;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 1px 6px rgba(0,0,0,.06);
  }}
  .logo {{
    font-size: 1.6rem;
    font-weight: 900;
    color: #F5A623;
    letter-spacing: -0.5px;
  }}
  .tagline {{
    font-size: 0.8rem;
    color: #999;
    margin-top: 2px;
  }}
  .search-row {{
    margin-top: 10px;
    display: flex;
    gap: 8px;
    max-width: 480px;
    margin-left: auto;
    margin-right: auto;
  }}
  #search {{
    flex: 1;
    padding: 9px 14px;
    border: 1.5px solid #e0e0e0;
    border-radius: 22px;
    font-size: 0.88rem;
    outline: none;
    transition: border-color .2s;
  }}
  #search:focus {{ border-color: #F5A623; }}
  .count-label {{
    font-size: 0.8rem;
    color: #aaa;
    text-align: center;
    padding: 10px 0 4px;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(155px, 1fr));
    gap: 12px;
    padding: 12px 14px 24px;
    max-width: 640px;
    margin: 0 auto;
  }}
  .card {{
    background: #fff;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 6px rgba(0,0,0,.07);
    display: flex;
    flex-direction: column;
  }}
  .card img {{
    width: 100%;
    aspect-ratio: 1 / 1;
    object-fit: cover;
    background: #f0f0f0;
  }}
  .card.no-img img {{ display: none; }}
  .card-body {{
    padding: 10px 10px 12px;
    display: flex;
    flex-direction: column;
    flex: 1;
  }}
  .badge {{
    display: inline-block;
    background: #FFF8E1;
    color: #E65100;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    margin-bottom: 6px;
    align-self: flex-start;
  }}
  .name {{
    font-size: 0.82rem;
    line-height: 1.45;
    color: #333;
    flex: 1;
    margin-bottom: 10px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .btn {{
    display: block;
    text-align: center;
    background: #FF6F00;
    color: #fff;
    text-decoration: none;
    padding: 8px 6px;
    border-radius: 9px;
    font-size: 0.78rem;
    font-weight: 700;
    transition: background .15s;
  }}
  .btn:hover {{ background: #e65100; }}
  .empty {{
    text-align: center;
    padding: 60px 20px;
    color: #bbb;
    font-size: 0.9rem;
    grid-column: 1 / -1;
  }}
  footer {{
    text-align: center;
    padding: 20px 16px 36px;
    color: #ccc;
    font-size: 0.72rem;
  }}
  .disclosure {{
    margin-top: 8px;
    font-size: 0.68rem;
    color: #bbb;
    max-width: 320px;
    margin-left: auto;
    margin-right: auto;
    line-height: 1.5;
  }}
  #no-result {{
    display: none;
    text-align: center;
    padding: 40px;
    color: #bbb;
    font-size: 0.88rem;
    grid-column: 1/-1;
  }}
</style>
</head>
<body>

<header>
  <div class="logo">🍯 꿀픽</div>
  <div class="tagline">보다가 이게 뭐야 싶은 것들만</div>
  <div class="search-row">
    <input type="search" id="search" placeholder="코드(예: 001) 또는 상품명 검색" autocomplete="off" inputmode="search">
  </div>
</header>

<div class="count-label" id="count-label">상품 {count}개</div>

<div class="grid" id="grid">
{cards}
  <p id="no-result">검색 결과가 없습니다</p>
</div>

<footer>
  <p>© 꿀픽</p>
  {disclosure}
</footer>

<script>
  const input = document.getElementById('search');
  const cards = Array.from(document.querySelectorAll('.card'));
  const noResult = document.getElementById('no-result');
  const countLabel = document.getElementById('count-label');

  input.addEventListener('input', () => {{
    const raw = input.value.trim();
    const q = raw.replace(/[\\[\\]]/g, '').toLowerCase();
    let visible = 0;

    cards.forEach(c => {{
      const match = !q || c.dataset.code.startsWith(q) || c.dataset.name.includes(q);
      c.style.display = match ? '' : 'none';
      if (match) visible++;
    }});

    noResult.style.display = visible === 0 ? 'block' : 'none';
    countLabel.textContent = q ? `${{visible}}개 검색됨` : `상품 ${{cards.length}}개`;
  }});

  // URL 해시로 바로 이동: index.html#001
  const hash = location.hash.replace('#', '').replace(/[\\[\\]]/g, '');
  if (hash) {{
    input.value = hash;
    input.dispatchEvent(new Event('input'));
    const target = document.querySelector(`.card[data-code="${{hash.padStart(3,'0')}}"]`);
    if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
  }}
</script>

</body>
</html>
"""


def main():
    products = get_all()
    html = build_html(products)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"생성 완료: {OUTPUT_PATH}")
    print(f"상품 {len(products)}개 포함")
    if products:
        print("코드 목록:", ", ".join(f"[{p['code']}]" for p in sorted(products, key=lambda x: x['code'])))


if __name__ == "__main__":
    main()
