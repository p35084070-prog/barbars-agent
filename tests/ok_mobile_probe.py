"""Разведка: что отдаёт ОК на мобильном UA для игры «Варвары».

Проверяем несколько URL и ищем в HTML признаки iframe/игрового хоста,
а также текст заглушки «Недоступно на данной платформе».
"""
from __future__ import annotations

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

URLS = [
    "https://ok.ru/game/barbars",
    "https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512",
    "https://m.ok.ru/game/barbars",
    "https://ok.ru/dk?st.cmd=appMain&st.appId=128512",
    "https://ok.ru/app/128512",
]

PATTERNS = [
    r"Недоступно на данной платформе",
    r"<iframe[^>]*>",
    r"https?://[^\"'\\\s>]+(?:barbar|overmobile)[^\"'\\\s>]*",
    r"data-app-client=\"[^\"]+\"",
    r"\"appUrl\"\s*:\s*\"[^\"]+\"",
    r"\"url\"\s*:\s*\"https?://[^\"]+\"",
    r"m\.ok\.ru[^\"'\\\s]*",
]


def main() -> None:
    for ua_name, ua in (("iphone", IPHONE_UA), ("android", ANDROID_UA)):
        print(f"===== UA {ua_name} =====")
        for url in URLS:
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": ua, "Accept-Language": "ru-RU,ru;q=0.9"},
                    timeout=25,
                    allow_redirects=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"-- {url}: ОШИБКА {exc}")
                continue
            html = resp.text
            print(f"-- {url} -> {resp.status_code} len={len(html)} final={resp.url}")
            for pat in PATTERNS:
                found = re.findall(pat, html, re.IGNORECASE)
                uniq = list(dict.fromkeys(found))[:6]
                if uniq:
                    print(f"     [{pat}] {uniq}")


if __name__ == "__main__":
    sys.exit(main())
