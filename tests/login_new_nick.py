"""Пытается войти с новым ником: сервер может сам предложить регистрацию."""
from __future__ import annotations

import re
import secrets

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

LOGIN = "Fire White"
PASSWORD = "Fw" + secrets.token_urlsafe(12)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
resp = session.get("https://barbars.ru/login", timeout=25)
form = re.search(r'<form action="([^"]+)"[^>]*method="post"', resp.text)
print("форма входа:", form.group(1) if form else None)
hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"', resp.text))
print("скрытые поля:", hidden)

data = {"login": LOGIN, "password": PASSWORD}
data.update(hidden)
action = "https://barbars.ru/" + form.group(1).lstrip("/")
res = session.post(action, data=data, timeout=25, headers={"Referer": resp.url})
print("ответ:", res.status_code, len(res.text), res.url)
print("форма регистрации:", "registrationForm" in res.text)
text = re.sub(r"<script.*?</script>", " ", res.text, flags=re.IGNORECASE | re.DOTALL)
text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
text = re.sub(r"<[^>]+>", " ", text)
print("текст:", " ".join(text.split())[:600])
for tag in re.findall(r"<(?:input|select)[^>]*>", res.text, re.IGNORECASE):
    print("   поле:", " ".join(tag.split()))
print("пароль:", PASSWORD)
