"""Проверяет, есть ли на сайте barbars.ru вход через ОК (OAuth/соцсеть)."""
from __future__ import annotations

import re

import requests

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

resp = requests.get("https://barbars.ru/", headers={"User-Agent": MOBILE_UA}, timeout=30)
html = resp.text
print("status", resp.status_code, "len", len(html))

pats = [
    r"[^\"'<>]{0,100}(?:ok\.ru|однокласс|Однокласс)[^\"'<>]{0,100}",
    r"[^\"'<>]{0,80}(?:oauth|social|auth\?|login)[^\"'<>]{0,100}",
    r"href=\"[^\"]*(?:login|auth|enter)[^\"]*\"",
]
for pat in pats:
    found = list(dict.fromkeys(re.findall(pat, html, re.IGNORECASE)))[:12]
    print(f"--- {pat}")
    for item in found:
        print("   ", " ".join(item.split())[:180])
