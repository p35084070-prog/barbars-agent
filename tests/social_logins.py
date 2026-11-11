"""Проверяет социальные входы barbars.ru (odnoklassnikilogin и др.)."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

PATHS = [
    "spaceslogin",
    "odnoklassnikilogin",
    "mailrulogin",
    "mailcataloglogin",
    "moimirlogin",
]

for path in PATHS:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    try:
        resp = session.get(f"https://barbars.ru/{path}", timeout=25, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{path}: ОШИБКА {exc}")
        continue
    print(f"--- {path}: {resp.status_code} final={resp.url} len={len(resp.text)}")
    print("    цепочка:", [r.status_code for r in resp.history])
    for r in resp.history:
        print("      ->", r.status_code, r.headers.get("location", "")[:160])
    body = resp.text
    print("    текст:", " ".join(body.replace("<", " <").split())[:300])
