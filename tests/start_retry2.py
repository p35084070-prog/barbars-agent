"""Пробует разные формы входа в «долину варваров»/регистрацию."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def report(label: str, resp: requests.Response) -> None:
    body = resp.text
    print(
        f"{label:40} -> {resp.status_code} len={len(body)} url={resp.url} "
        f"долина={'Долина варваров' in body} форма={'registrationForm' in body}"
    )


session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})

resp = session.get("https://barbars.ru/", timeout=25)
report("GET /", resp)
href = re.search(r'href="(start[^"]+)"', resp.text)
print("   start href:", href.group(1) if href else None)
if href:
    report("GET /" + href.group(1), session.get("https://barbars.ru/" + href.group(1), timeout=25))

sid = session.cookies.get("JSESSIONID")
print("   JSESSIONID:", sid)
if sid:
    report(f"GET /start;jsessionid={sid}", session.get(f"https://barbars.ru/start;jsessionid={sid}", timeout=25))
    report("GET /registration;jsessionid", session.get(f"https://barbars.ru/registration;jsessionid={sid}", timeout=25))

report("GET /;jsessionid", session.get(f"https://barbars.ru/;jsessionid={sid}", timeout=25))
report("GET /registration (в той же сессии)", session.get("https://barbars.ru/registration", timeout=25))
