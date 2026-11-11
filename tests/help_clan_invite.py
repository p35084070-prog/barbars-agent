"""Ищем в справке игры, как вступают/приглашают в клан."""
from __future__ import annotations

import re
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})

index = session.get("https://barbars.ru/help/0/help", timeout=30)
print("справка:", index.status_code, len(index.text))
links = [
    urljoin(index.url, href)
    for href in re.findall(r'href="([^"]+)"', index.text)
    if "help" in href.lower()
]
print("разделов:", len(links))
for url in links[:60]:
    try:
        page = session.get(url, timeout=20)
    except Exception:  # noqa: BLE001
        continue
    text = re.sub(r"<script.*?</script>", " ", page.text, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    if re.search(r"приглаш|вступить в клан|в клан", text, re.IGNORECASE):
        print(f"=== {url}")
        for item in re.findall(r"[^.]{0,120}(?:приглаш|вступить в клан|в клан)[^.]{0,160}", text, re.IGNORECASE):
            print("   ", " ".join(item.split())[:260])
