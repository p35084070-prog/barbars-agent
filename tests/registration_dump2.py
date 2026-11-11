"""Дамп страницы регистрации barbars.ru (нужна сессия: сначала /start)."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
session.get("https://barbars.ru/start", timeout=30)
resp = session.get("https://barbars.ru/registration", timeout=30)
print(resp.status_code, resp.url, len(resp.text))
print(resp.text)
