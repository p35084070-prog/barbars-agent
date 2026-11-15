"""Откуда в игре серебро: сырой лот аукциона ресурсов и разделы справки.

Печатает:
  * сырой HTML одного лота бутылочек (как игра показывает цену);
  * список страниц справки (/help) — где может быть раздел про серебро;
  * текст справки по найденным разделам с упоминанием серебра.

Запуск: python tools\\probe_silver.py <ник> <пароль>
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

    bazaar = session.get("https://barbars.ru/trade/bazaar", timeout=25)
    print("\n=== аукцион ресурсов: сырой первый лот")
    blocks = bazaar.text.split('<div class="hr"></div>')
    for chunk in blocks:
        if "money_gold" in chunk or "money_silver" in chunk:
            print(chunk[:2500])
            break
    print("\n--- ссылки страницы аукциона ресурсов")
    for tag in re.findall(r"<a[^>]*>", bazaar.text, re.I):
        if any(k in tag.lower() for k in ("filter", "bazaar", "lot", "resource", "iron", "mifril", "potion")):
            print("  ", " ".join(tag.split()))

    print("\n=== справка игры")
    help_page = session.get("https://barbars.ru/help/0", timeout=25)
    links = sorted(set(re.findall(r'href="(?:\.\./)*(help/0/([a-z_]+))"', help_page.text, re.I)))
    print("  разделы:", [l for _u, l in links][:60])
    for _u, slug in links:
        p = session.get(f"https://barbars.ru/help/0/{slug}", timeout=25)
        t = text_of(p.text)
        if "серебр" in t.lower():
            print(f"\n  --- help/0/{slug}: {t[:700]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
