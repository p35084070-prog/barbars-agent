"""Где можно купить снаряжение 25 уровня не дороже 1 золота за вещь.

Печатает:
  * товары «Магазина снаряжения» (разбором barbars.pages — тем же кодом,
    что и у агента);
  * лоты «Аукциона вещей» (/trade/auction) с ценой в золоте/серебре.

Запуск: python tools\\probe_gear_sources.py <ник> <пароль>
"""
from __future__ import annotations

import re
import sys

import requests

from barbars import pages

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
SETS = ["", "goliaf", "atlant", "veteran"]


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
    hero = session.get("https://barbars.ru/user", timeout=25)
    print("герой:", text_of(hero.text)[:220])

    for set_name in SETS:
        url = "https://barbars.ru/trade/auction/shop"
        if set_name:
            url += f"/0/{set_name}"
        r = session.get(url, timeout=25)
        items = pages.parse_shop_gear(r.text)
        print(f"\n=== магазин, набор {set_name or 'Берсерк'} :: {len(items)} товаров")
        for it in items:
            print(
                f"  {it['name'][:34]:36} ур {it['level']:>3} +{it['bonus']:>3} "
                f"тир {it['tier'][:8]:9} {it['gold']} зол / {it['silver']} сер "
                f"id={it['item_id']}"
            )
        if not items:
            print("   (разбор ничего не нашёл; текст страницы:", text_of(r.text)[:160], ")")

    for path in ("/trade/auction", "/trade/auction/0/1"):
        r = session.get("https://barbars.ru" + path, timeout=25)
        lots = pages.parse_auction_items(r.text)
        print(f"\n=== аукцион вещей {path} :: {len(lots)} лотов")
        for lot in lots[:40]:
            print(
                f"  {lot['name'][:32]:34} ур {lot['level']:>3} тир {lot['tier'][:8]:9} "
                f"{lot['gold']} зол / {lot['silver']} сер id={lot['item_id']}"
            )
        if not lots:
            print("   (лотов не найдено; текст:", text_of(r.text)[:200], ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
