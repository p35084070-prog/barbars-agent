"""Полный разбор гостевой страницы /authorization (там есть «Вход» и «Регистрация»)."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
resp = session.get("https://barbars.ru/guild/16675", timeout=25)
print("url:", resp.url, resp.status_code, len(resp.text))
print(resp.text)
