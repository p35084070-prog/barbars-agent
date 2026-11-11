"""Находит href кнопки «Регистрация» на странице для гостей."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
session.get("https://barbars.ru/", timeout=25)
resp = session.get("https://barbars.ru/guild/16675", timeout=25)

for href, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.IGNORECASE | re.DOTALL):
    clean = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    print(f"{href}   | {clean[:60]}")

print("=== регистрация в html ===")
for item in re.findall(r"[^\"'<>]{0,120}[Рр]егистрац[^\"'<>]{0,120}", resp.text):
    print("   ", " ".join(item.split())[:200])
