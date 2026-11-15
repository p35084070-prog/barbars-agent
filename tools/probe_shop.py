"""Проба «Магазина снаряжения»: какие товары есть и по какой цене.

Печатает по каждому набору: название, уровень, бонус, цену (золото/серебро).
Нужно, чтобы понять, укладывается ли покупка в лимит «не дороже 1 золота за вещь».

Запуск: python tools\\probe_shop.py <ник> <пароль> [набор]
"""
from __future__ import annotations

import re
import sys

import requests

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


def parse_items(html: str) -> list[dict[str, str]]:
    out = []
    for chunk in re.split(r"(?=<div class=\"?l\b)", html):
        m = re.search(r'href="([^"]*shop/item/id/(\d+)[^"]*)"[^>]*>(.*?)</a>', chunk, re.S | re.I)
        if not m:
            continue
        name = " ".join(re.sub(r"<[^>]+>", " ", m.group(3)).split())
        level = re.search(r"(\d+)\s*ур", text_of(chunk))
        bonus = re.search(r"Лучше\s*\(\s*\+(\d+)\s*\)", chunk)
        price = text_of(chunk)
        gold = silver = 0
        for icon, num in re.findall(
            r"icons/(money_gold|money_silver)\.png\"[^>]*>\s*<span>([\d.,]+)</span>", chunk
        ):
            val = float(num.replace(",", ".").replace(" ", ""))
            if icon == "money_gold":
                gold = int(val)
            else:
                silver = int(val)
        out.append(
            {
                "name": name,
                "id": m.group(2),
                "level": level.group(1) if level else "?",
                "bonus": bonus.group(1) if bonus else "?",
                "gold": str(gold),
                "silver": str(silver),
                "price_text": price[-160:],
            }
        )
    return out


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    only = sys.argv[3] if len(sys.argv) > 3 else None
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
    print("герой:", text_of(hero.text)[:200])
    for set_name in SETS:
        if only and set_name != only:
            continue
        url = "https://barbars.ru/trade/auction/shop"
        if set_name:
            url += f"/0/{set_name}"
        r = session.get(url, timeout=25)
        items = parse_items(r.text)
        print(f"\n=== набор {set_name or 'набор Берсерка'} :: {r.status_code} {r.url} :: {len(items)} товаров")
        for it in items:
            print(
                f"  {it['name'][:34]:36} ур {it['level']:>3} +{it['bonus']:>3} "
                f"цена: {it['gold']} зол / {it['silver']} сер"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
