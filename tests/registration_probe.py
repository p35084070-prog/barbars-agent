"""Ищет страницу регистрации barbars.ru и разбирает её поля."""
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

resp = session.get("https://barbars.ru/", timeout=30)
print("root:", resp.status_code, resp.url, len(resp.text))
print("---- root html ----")
print(resp.text[:2500])

login_url = urljoin(resp.url, "login")
page = session.get(login_url, timeout=30)
print("---- login html ----")
print(page.text[:4000])

links = re.findall(r'href="([^"]+)"', page.text)
print("---- ссылки ----")
for link in links:
    print("   ", link)

for candidate in ("registration", "register", "signup", "signUp", "newUser", "registration;jsessionid"):
    url = urljoin(page.url, candidate)
    try:
        r = session.get(url, timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(candidate, "ОШИБКА", exc)
        continue
    print(f"{candidate} -> {r.status_code} {r.url} len={len(r.text)}")
