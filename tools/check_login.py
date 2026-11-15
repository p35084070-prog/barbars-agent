"""Проверка входа героя на barbars.ru (без браузера).

Печатает, вошёл ли герой, и его страницу /user.
Запуск: python tools\\check_login.py <ник> <пароль>
"""
from __future__ import annotations

import re
import sys

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    for candidate in {nick, nick.lower(), nick.title()}:
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
        page = session.get("https://barbars.ru/login", timeout=25)
        form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
        if not form:
            print("форма входа не найдена")
            return 1
        action = "https://barbars.ru/" + form.group(1).lstrip("/")
        res = session.post(
            action,
            data={"login": candidate, "password": password},
            timeout=25,
            headers={"Referer": page.url},
        )
        body = text_of(res.text)
        ok = "Выход" in body or "Мой герой" in body or "Мой герой" in res.text
        print(f"вход как «{candidate}»: {'ОК' if ok else 'не удалось'}")
        print("  текст:", body[:220])
        if ok:
            hero = session.get("https://barbars.ru/user", timeout=25)
            print("  герой:", text_of(hero.text)[:300])
            ids = sorted(set(re.findall(r"/user/id/(\d+)", hero.text)))
            print("  user-id:", ids)
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
