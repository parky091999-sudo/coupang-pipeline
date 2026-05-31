import json

with open("data/products.json", encoding="utf-8") as f:
    products = json.load(f)

for p in products:
    print(f"상품: {p['name'][:50]}")
    print(f"가격: {p['price']} | mall: {p['mall_name']}")
    print(f"링크: {p['product_url'][:80]}")
    print()
