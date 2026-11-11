"""Перебор URL-вариантов запуска игры «Варвары» в ОК (мобильный UA).

Для каждого варианта смотрим, что вернул сервер: заглушка, «mob_only_app»,
либо признаки игрового клиента (iframe/canvas/игра).
"""
from __future__ import annotations

import re

import requests

ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

VARIANTS = [
    "https://ok.ru/game/barbars",
    "https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512",
    "https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512&st.appPlatform=android",
    "https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512&st.appPlatform=web",
    "https://ok.ru/game/barbars?st.appId=128512&st.cmd=appMain&st.refplace=218",
    "https://ok.ru/dk?st.cmd=appMain&st.appId=128512",
    "https://m.ok.ru/game/barbars",
    "https://m.ok.ru/game/barbars?st.cmd=appMain&st.appId=128512",
    "https://m.ok.ru/dk?st.cmd=appMain&st.appId=128512",
    "https://ok.ru/game/barbars?platform=android",
]

KEYS = [
    r"mob_only_app",
    r"Недоступно на данной платформе",
    r"Играть",
    r"data-view=\"[^\"]+\"",
    r"<canvas[^>]*>",
    r"https?://[^\"'\\\s<>]*(?:barbar|overmobile|html5|webgame)[^\"'\\\s<>]*",
    r"\"(?:webUrl|gameUrl|html5Url|launchUrl|deeplink|appUrl)\"\s*:\s*\"[^\"]{0,120}\"",
]


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": ANDROID_UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    for url in VARIANTS:
        try:
            resp = session.get(url, timeout=25, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001
            print(f"-- {url}\n   ОШИБКА {exc}")
            continue
        html = resp.text
        print(f"-- {url}\n   {resp.status_code} len={len(html)} final={resp.url}")
        for pat in KEYS:
            found = list(dict.fromkeys(re.findall(pat, html, re.IGNORECASE)))[:4]
            if found:
                print(f"     {pat} -> {found}")


if __name__ == "__main__":
    main()
