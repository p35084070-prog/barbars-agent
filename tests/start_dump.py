"""Печатает HTML стартовой страницы barbars.ru (/start) и ищет регистрацию."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
resp = session.get("https://barbars.ru/start", timeout=30)
print(resp.status_code, resp.url, len(resp.text))
print(resp.text)
print("======= поиск регистрации =======")
for url in (
    "https://barbars.ru/registration",
    "https://barbars.ru/reg",
    "https://barbars.ru/newplayer",
    "https://barbars.ru/register;jsessionid=",
    "https://barbars.ru/signup",
    "https://barbars.ru/create",
):
    try:
        r = session.get(url, timeout=15)
    except Exception as exc:  # noqa: BLE001
        print(url, "ОШИБКА", exc)
        continue
    print(url, "->", r.status_code, len(r.text))
