"""Перебор путей barbars.ru в поисках страницы регистрации."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

PATHS = [
    "welcome",
    "welcome?channelId=35",
    "landing",
    "landing?channelId=35",
    "intro",
    "intro?channelId=35",
    "newplayer",
    "new",
    "reg",
    "signup",
    "create",
    "game",
    "play",
    "start2",
    "authorization",
    "auth",
    "join",
    "about",
    "promo",
    "bonuses",
    "first",
    "begin",
    "demo",
    "fight",
    "user/register",
    "user/new",
    "account/register",
    "action/register",
]

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
for path in PATHS:
    url = f"https://barbars.ru/{path}"
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        print(f"{path:26} ОШИБКА {exc}")
        continue
    body = resp.text
    flags = []
    if "registrationForm" in body:
        flags.append("ФОРМА")
    if "Игровое имя" in body:
        flags.append("ПОЛЕ-НИК")
    if "Долина варваров" in body:
        flags.append("ДОЛИНА")
    if "Сразиться" in body:
        flags.append("БОЙ")
    if "Эта страница доступна только зарегистрированным" in body:
        flags.append("ГОСТЬ")
    if resp.status_code != 404 or flags:
        print(f"{path:26} {resp.status_code} len={len(body):6} url={resp.url[:60]:60} {' '.join(flags)}")
