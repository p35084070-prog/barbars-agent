"""Сохраняет HTML страницы ОК (мобильный UA) для ручного разбора."""
from __future__ import annotations

import re
import sys

import requests

ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

URL = "https://m.ok.ru/game/barbars"
OUT = "ok_mobile_barbars.html"


def main() -> None:
    resp = requests.get(
        URL,
        headers={"User-Agent": ANDROID_UA, "Accept-Language": "ru-RU,ru;q=0.9"},
        timeout=30,
    )
    html = resp.text
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"status={resp.status_code} len={len(html)} -> {OUT}")
    for pat in [
        r"<iframe[^>]*>",
        r"Недоступно[^<]{0,80}",
        r"мобильн[^<]{0,120}",
        r"appId[^,&\"'<]{0,20}",
        r"https?://[^\"'\\\s<>]*(?:barbar|overmobile|cdn-vk)[^\"'\\\s<>]*",
        r"class=\"[^\"]*(?:game|app)[^\"]*\"",
    ]:
        found = list(dict.fromkeys(re.findall(pat, html, re.IGNORECASE)))[:10]
        if found:
            print(f"[{pat}]")
            for item in found:
                print("   ", item[:200])


if __name__ == "__main__":
    sys.exit(main())
