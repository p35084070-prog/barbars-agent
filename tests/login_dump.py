"""Печатает HTML страницы входа barbars.ru целиком (маленькая страница)."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
resp = session.get("https://barbars.ru/login", timeout=30)
print(resp.status_code, resp.url)
print(resp.text)
