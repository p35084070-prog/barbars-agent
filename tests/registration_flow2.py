"""Проверяет путь к регистрации через гостевую страницу с кнопкой «Регистрация»."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})

guest = session.get("https://barbars.ru/guild/16675", timeout=25)
print("гость:", guest.status_code, len(guest.text))

reg = session.get("https://barbars.ru/registration", timeout=25, headers={"Referer": guest.url})
print("регистрация:", reg.status_code, len(reg.text), "форма:", "registrationForm" in reg.text)
if "registrationForm" in reg.text:
    for tag in re.findall(r"<(?:input|select)[^>]*>", reg.text, re.IGNORECASE):
        print("   ", " ".join(tag.split()))
    for opt in re.findall(r"<option[^>]*>", reg.text, re.IGNORECASE):
        print("    option:", " ".join(opt.split()))
else:
    text = re.sub(r"<[^>]+>", " ", reg.text)
    print("   текст:", " ".join(text.split())[:300])
