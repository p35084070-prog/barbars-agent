"""Матрица способов попасть на форму регистрации barbars.ru."""
from __future__ import annotations

import requests

MOBILE = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

TARGETS = [
    ("https://barbars.ru/start", MOBILE),
    ("https://barbars.ru/start", DESKTOP),
    ("http://barbars.ru/start", MOBILE),
    ("https://www.barbars.ru/start", MOBILE),
    ("https://barbars.ru/registration", MOBILE),
    ("https://barbars.ru/Registration", MOBILE),
    ("https://barbars.ru/registration/", MOBILE),
    ("https://barbars.ru/registration?new=1", MOBILE),
    ("https://barbars.ru/start?new=1", MOBILE),
    ("https://barbars.ru/start?ref=ok", MOBILE),
    ("https://barbars.ru/start?from=mail", MOBILE),
    ("https://barbars.ru/start?from=ok", MOBILE),
]

for url, ua in TARGETS:
    session = requests.Session()
    session.headers.update({"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"})
    try:
        resp = session.get(url, timeout=25, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{url} [{'mob' if ua is MOBILE else 'desk'}] ОШИБКА {exc}")
        continue
    body = resp.text
    print(
        f"{url} [{'mob' if ua is MOBILE else 'desk'}] -> {resp.status_code} len={len(body)} "
        f"url={resp.url} долина={'Долина варваров' in body} форма={'registrationForm' in body}"
    )
