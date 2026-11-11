"""Разбирает страницу регистрации barbars.ru (/start)."""
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

resp = session.get("https://barbars.ru/start", timeout=30)
print("status", resp.status_code, resp.url, len(resp.text))
html = resp.text

print("---- forms ----")
for form in re.findall(r"<form[^>]*>", html, re.IGNORECASE):
    print("   ", form)

print("---- inputs ----")
for tag in re.findall(r"<input[^>]*>", html, re.IGNORECASE):
    print("   ", " ".join(tag.split()))

print("---- selects ----")
for block in re.findall(r"<select[^>]*>.*?</select>", html, re.IGNORECASE | re.DOTALL):
    print("   ", " ".join(block.split())[:400])

print("---- текст ----")
text = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
text = re.sub(r"<[^>]+>", " ", text)
print(" ".join(text.split())[:1500])

print("---- ссылки ----")
for link in re.findall(r'href="([^"]+)"', html):
    print("   ", urljoin(resp.url, link))
