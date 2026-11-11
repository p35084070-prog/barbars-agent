"""Читает справку о кланах целиком."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
page = session.get("https://barbars.ru/help/0/clans", timeout=30)
text = re.sub(r"<script.*?</script>", " ", page.text, flags=re.I | re.S)
text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
text = re.sub(r"<[^>]+>", "\n", text)
lines = [line.strip() for line in text.splitlines() if line.strip()]
print("\n".join(lines[:120]))
