"""Снимает форму регистрации barbars.ru: вход с новым ником → форма регистрации.

Печатает action, скрытые поля, имена полей и варианты select'ов —
это нужно, чтобы понять, что за класс/регион/пол выбирать новому герою.

Запуск: python tools\\probe_registration_form.py [ник]
"""
from __future__ import annotations

import re
import secrets
import sys

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
LOGIN = sys.argv[1] if len(sys.argv) > 1 else "Probe Hero " + secrets.token_hex(3)
PASSWORD = "Ph" + secrets.token_urlsafe(10)


def strip(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def main() -> None:
    print(f"ник: {LOGIN!r} пароль: {PASSWORD}")
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    resp = session.get("https://barbars.ru/login", timeout=25)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', resp.text)
    print("форма входа:", form.group(1) if form else None)
    hidden = dict(re.findall(r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"', resp.text))
    print("скрытые:", hidden)

    data = {"login": LOGIN, "password": PASSWORD}
    data.update(hidden)
    action = "https://barbars.ru/" + (form.group(1) if form else "login").lstrip("/")
    res = session.post(action, data=data, timeout=25, headers={"Referer": resp.url})
    print("ответ:", res.status_code, len(res.text), res.url)
    print("есть registrationForm:", "registrationForm" in res.text)
    print("текст:", strip(res.text)[:700])
    print("--- поля ---")
    for tag in re.findall(r"<(?:input|select|textarea)[^>]*>", res.text, re.I):
        print("   ", " ".join(tag.split()))
    print("--- select-опции ---")
    for name in re.findall(r'<select[^>]*name="([^"]+)"', res.text, re.I):
        block = re.search(
            rf'<select[^>]*name="{re.escape(name)}"[^>]*>(.*?)</select>', res.text, re.S | re.I
        )
        opts = []
        if block:
            for opt in re.findall(r"<option[^>]*>", block.group(1), re.I):
                value = re.search(r'value="([^"]*)"', opt)
                text = " ".join(re.sub(r"<[^>]+>", " ", opt).split())
                opts.append((value.group(1) if value else "", text))
        print(f"   {name}: {opts}")
    print("--- формы ---")
    for tag in re.findall(r"<form[^>]*>", res.text, re.I):
        print("   ", " ".join(tag.split()))
    print("--- ссылки ---")
    for tag in re.findall(r"<a[^>]*href=\"([^\"]+)\"[^>]*>", res.text, re.I)[:40]:
        print("   ", tag)


if __name__ == "__main__":
    main()
