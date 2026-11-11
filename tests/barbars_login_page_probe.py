"""Смотрит страницу логина barbars.ru: есть ли кнопки входа через соцсети (ОК)."""
from __future__ import annotations

import re
from urllib.parse import urljoin

import requests

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": MOBILE_UA, "Accept-Language": "ru-RU,ru;q=0.9"})

resp = session.get("https://barbars.ru/", timeout=30)
print("root", resp.status_code, resp.url, len(resp.text))
login_href = re.search(r'href="(login[^"]*)"', resp.text)
if login_href:
    url = urljoin(resp.url, login_href.group(1))
else:
    url = urljoin(resp.url, "login")
page = session.get(url, timeout=30)
print("login", page.status_code, page.url, len(page.text))

pats = [
    r"[^\"'<>]{0,90}(?:ok\.ru|однокласс|ОК\.|ВКонтакте|Google)[^\"'<>]{0,90}",
    r"<img[^>]{0,200}(?:ok|social|vk|google)[^>]{0,120}>",
    r"href=\"[^\"]{0,160}\"",
    r"<button[^>]{0,160}>",
]
for pat in pats:
    found = list(dict.fromkeys(re.findall(pat, page.text, re.IGNORECASE)))[:25]
    print(f"--- {pat}")
    for item in found:
        print("   ", " ".join(item.split())[:180])
