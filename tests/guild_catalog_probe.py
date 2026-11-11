"""Ищем каталог кланов и кнопку вступления."""
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

for path in (
    "rating/guild",
    "guild/search",
    "guilds",
    "guild/list",
    "guild/16675",
    "users/search?type=guild",
):
    try:
        resp = session.get(f"https://barbars.ru/{path}", timeout=25)
    except Exception as exc:  # noqa: BLE001
        print(path, "ОШИБКА", exc)
        continue
    body = resp.text
    print(f"--- {path}: {resp.status_code} len={len(body)} url={resp.url}")
    hits = re.findall(r"[^\"'<>]{0,70}(?:вступи|Приглаш|приглаш|join)[^\"'<>]{0,70}", body, re.I)
    for item in list(dict.fromkeys(hits))[:6]:
        print("    ", " ".join(item.split())[:150])
    if path in ("rating/guild", "guild/16675"):
        for href, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.I | re.S):
            clean = " ".join(re.sub(r"<[^>]+>", " ", text).split())
            if clean and ("guild" in href or "вступ" in clean.lower() or "клан" in clean.lower()):
                print("    ссылка:", href, "|", clean[:60])
