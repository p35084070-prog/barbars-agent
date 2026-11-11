"""Ищет ссылку на регистрацию: страница входа + справка."""
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

resp = session.get("https://barbars.ru/login", timeout=25)
print("login", resp.status_code, len(resp.text))
for link in re.findall(r'href="([^"]+)"', resp.text):
    print("   link:", urljoin(resp.url, link))
text = re.sub(r"<[^>]+>", " ", resp.text)
print("   текст:", " ".join(text.split())[:600])

for help_path in ("help", "help/0/registration", "help/0/register", "help/0/start", "help/0/nick"):
    url = urljoin(resp.url, help_path)
    try:
        r = session.get(url, timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(help_path, "ОШИБКА", exc)
        continue
    txt = re.sub(r"<[^>]+>", " ", r.text)
    print(f"--- {url} -> {r.status_code} len={len(r.text)}")
    print("   ", " ".join(txt.split())[:400])
    for link in re.findall(r'href="([^"]+)"', r.text):
        if any(word in link.lower() for word in ("reg", "start", "new", "create", "signup")):
            print("    релевантная ссылка:", urljoin(r.url, link))
