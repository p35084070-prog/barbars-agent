"""Проходит туториал нового героя (демо-бой «Долина варваров»).

После регистрации герой попадает на страницу туториала: нужно отыграть
демо-бой («Бить варвара») и выйти через «Покинуть бой».

Запуск: python tools\\finish_tutorial.py <ник> <пароль>
"""
from __future__ import annotations

import re
import sys
import time
from urllib.parse import urljoin

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


def find_href(html: str, *words: str) -> str | None:
    for tag in re.findall(r"<a[^>]*>", html, re.I):
        low = tag.lower()
        if all(w.lower() in low for w in words):
            m = re.search(r'href="([^"]+)"', tag, re.I)
            if m:
                return m.group(1)
    return None


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    page = session.get("https://barbars.ru/login", timeout=25)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
    action = "https://barbars.ru/" + form.group(1).lstrip("/")
    res = session.post(
        action, data={"login": nick, "password": password},
        timeout=25, headers={"Referer": page.url},
    )
    print("вход:", res.status_code, res.url)
    for step in range(80):
        body = text_of(res.text)
        print(f"шаг {step}: {res.url} :: {body[:110]}")
        if "Мой герой" in body and "Выход" in body:
            print("герой готов")
            return 0
        href = find_href(res.text, "damageOgreLink") or find_href(res.text, "attackLink")
        if href and "Покинуть" not in body:
            res = session.get(urljoin(res.url, href), timeout=25, headers={"Referer": res.url})
            time.sleep(1.0)
            continue
        leave = find_href(res.text, "Покинуть бой")
        if leave:
            res = session.get(urljoin(res.url, leave), timeout=25, headers={"Referer": res.url})
            time.sleep(1.0)
            continue
        for word in ("Продолжить", "Далее", "Принять", "Выйти"):
            href = find_href(res.text, word)
            if href:
                res = session.get(urljoin(res.url, href), timeout=25, headers={"Referer": res.url})
                time.sleep(1.0)
                break
        else:
            time.sleep(2)
    print("туториал не завершён")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
