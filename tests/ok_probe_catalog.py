"""Разведка каталога ОК: ищем веб-версию игры «Варвары» и её точки входа.

Цель: понять, есть ли у игры appId=128512 веб-клиент (data-app-client != noapp),
какие URL/deeplink'и она использует и куда ведёт кнопка «Играть».
"""
from __future__ import annotations

import json
import re
import sys

import requests

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

URLS = [
    "https://ok.ru/apps?st.query=%D0%92%D0%B0%D1%80%D0%B2%D0%B0%D1%80%D1%8B",
    "https://ok.ru/games?st.query=%D0%92%D0%B0%D1%80%D0%B2%D0%B0%D1%80%D1%8B",
    "https://ok.ru/game/barbars",
    "https://m.ok.ru/game/barbars",
    "https://ok.ru/dk?st.cmd=appMain&st.appId=128512",
]

PATTERNS = {
    "app-client": r'data-app-client="([^"]+)"',
    "appid": r'"appId"\s*:\s*"?(\d+)',
    "play-uri": r'"(?:playUri|launchUri|launchUrl|webUrl|webGameUrl|gameUrl|appUrl|url)"\s*:\s*"(https?://[^"]{4,200})"',
    "deeplink": r'"(?:deeplink|deepLink|schemeUri)"\s*:\s*"([^"]{4,200})"',
    "store": r'"(?:storeUrl|marketUrl|downloadUrl)"\s*:\s*"([^"]{4,200})"',
    "platform": r'"(?:platform|appPlatform|platforms)"\s*:\s*"?([^",]{2,40})',
    "barbar-host": r'https?://[^"\'\\<>\s]*(?:barbar|playok|overmobile)[^"\'\\<>\s]{0,60}',
    "game-url-host": r'https?://[^"\'\\<>\s]*game[^"\'\\<>\s]{0,60}',
}


def probe(ua_name: str, ua: str) -> None:
    print(f"\n########## UA={ua_name}")
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": ua,
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    for url in URLS:
        try:
            r = sess.get(url, timeout=30, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001
            print(f"-- {url}: ОШИБКА {exc}")
            continue
        html = r.text
        print(f"-- {url}\n   {r.status_code} len={len(html)} final={r.url}")
        for name, pat in PATTERNS.items():
            found = list(dict.fromkeys(re.findall(pat, html, re.IGNORECASE)))[:6]
            if found:
                print(f"     {name}: {found}")


def main() -> None:
    probe("iphone", IPHONE_UA)
    probe("android", ANDROID_UA)
    probe("desktop", DESKTOP_UA)


if __name__ == "__main__":
    sys.exit(main())
