"""Проверяет последовательность для получения формы регистрации."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5..0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
).replace("5.1", "5.0")

SEQUENCES = {
    "сразу /registration": ["/registration"],
    "сначала /start": ["/start", "/registration"],
    "сначала /": ["/", "/registration"],
    "сначала /login": ["/login", "/registration"],
    "/start, /start, /registration": ["/start", "/start", "/registration"],
}

for label, steps in SEQUENCES.items():
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    sizes = []
    for step in steps:
        resp = session.get("https://barbars.ru" + step, timeout=25)
        sizes.append((step, resp.status_code, len(resp.text), "registrationForm" in resp.text))
    print(f"{label:32} -> {sizes}")
