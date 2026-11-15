"""Проба кошелька и страницы товара магазина.

Печатает:
  * «деньги» и «ресурсы» со страницы героя (/user) — сколько золота и серебра;
  * текст страницы товара магазина (как игра показывает цену).

Запуск: python tools\\probe_wallet.py <ник> <пароль> [item_id]
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
    item_id = sys.argv[3] if len(sys.argv) > 3 else "40120996"
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    page = session.get("https://barbars.ru/login", timeout=25)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
    res = session.post(
        "https://barbars.ru/" + form.group(1).lstrip("/"),
        data={"login": nick, "password": password},
        timeout=25, headers={"Referer": page.url},
    )
    print("вход:", res.status_code, res.url)
    hero = session.get("https://barbars.ru/user", timeout=25)
    body = text_of(hero.text)
    print("герой:", body[:400])
    for key in ("деньги", "ресурсы", "золото", "серебро"):
        for m in re.finditer(rf"{key}\s*:?\s*([^ ]+(?:\s+[^ ]+){{0,3}})", body, re.I):
            print(f"  {key}: {m.group(1)[:80]}")
            break
    res = session.get(f"https://barbars.ru/trade/auction/shop/item/id/{item_id}", timeout=25)
    print("\nстраница товара:", res.status_code, res.url)
    print(text_of(res.text)[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
