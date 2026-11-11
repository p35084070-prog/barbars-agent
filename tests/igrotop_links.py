"""Ищет партнёрскую ссылку на «Варвары» в каталоге igrotop.mobi."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
page = session.get("http://igrotop.mobi/", timeout=25)
ids = sorted({int(m) for m in re.findall(r"go/game/(\d+)/", page.text)})
print("идентификаторы игр:", ids)

for gid in ids:
    try:
        resp = session.get(f"http://igrotop.mobi/go/game/{gid}/", timeout=20, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        print(gid, "ОШИБКА", exc)
        continue
    final = resp.url
    print(f"{gid:3} -> {final}  (len={len(resp.text)})")
    if "barbars" in final:
        print("   *** ВАРВАРЫ:", final)
        print("   цепочка:", [(r.status_code, r.headers.get('location', '')[:120]) for r in resp.history])
