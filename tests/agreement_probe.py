"""Проверяет страницу соглашения: есть ли кнопка принятия, открывающая регистрацию."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
resp = session.get("https://barbars.ru/help/0/agreement", timeout=25)
print("agreement:", resp.status_code, len(resp.text), resp.url)
for href, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.IGNORECASE | re.DOTALL):
    clean = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    print("   ссылка:", href, "|", clean[:60])
for item in re.findall(r"[^\"'<>]{0,60}(?:приним|согласен|accept)[^\"'<>]{0,60}", resp.text, re.IGNORECASE):
    print("   совпадение:", " ".join(item.split())[:120])

reg = session.get("https://barbars.ru/registration", timeout=25)
print("registration после agreement:", reg.status_code, len(reg.text), "форма:", "registrationForm" in reg.text)
