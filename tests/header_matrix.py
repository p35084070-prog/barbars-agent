"""Ищет заголовок, из-за которого /start отдаёт «долину» или редирект."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

BASE = {"User-Agent": UA}
BROWSER = {
    **BASE,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
    "image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
}

CASES = {
    "только UA": BASE,
    "как браузер": BROWSER,
    "без Upgrade-Insecure-Requests": {k: v for k, v in BROWSER.items() if k != "Upgrade-Insecure-Requests"},
    "без Sec-Fetch": {k: v for k, v in BROWSER.items() if not k.startswith("Sec-Fetch")},
    "без sec-ch": {k: v for k, v in BROWSER.items() if not k.startswith("sec-ch")},
    "Accept без */*": {**BROWSER, "Accept": "text/html"},
}

for label, headers in CASES.items():
    session = requests.Session()
    session.headers.update(headers)
    resp = session.get("https://barbars.ru/start", timeout=25, allow_redirects=True)
    has_valley = "Долина варваров" in resp.text
    print(f"{label:32} -> {resp.status_code} url={resp.url} len={len(resp.text)} долина={has_valley}")
