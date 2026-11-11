"""Сохраняет страницу регистрации barbars.ru в файл для разбора."""
from __future__ import annotations

from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

OUT = Path(__file__).resolve().parents[1] / "knowledge" / "discovered" / "registration.html"

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
session.get("https://barbars.ru/start", timeout=30)
resp = session.get("https://barbars.ru/registration", timeout=30)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(resp.text, encoding="utf-8")
print(f"{resp.status_code} {resp.url} len={len(resp.text)} -> {OUT}")
