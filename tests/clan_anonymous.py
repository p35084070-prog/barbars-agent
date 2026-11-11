"""Анонимный вид страницы клана: есть ли кнопка «Вступить»."""
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
print("status", resp.status_code, len(resp.text))
text = re.sub(r"<script.*?</script>", " ", resp.text, flags=re.IGNORECASE | re.DOTALL)
text = re.sub(r"<[^>]+>", " ", text)
text = " ".join(text.split())
print(text[:1200])
for pat in ("Вступить", "вступ", "join", "Пригласить", "приглас", "Подать заявку", "заявк"):
    found = [m for m in re.findall(rf"[^\"'<>]{{0,90}}{pat}[^\"'<>]{{0,90}}", resp.text, re.IGNORECASE)]
    if found:
        print(f"--- «{pat}»:")
        for item in list(dict.fromkeys(found))[:6]:
            print("   ", " ".join(item.split())[:160])
