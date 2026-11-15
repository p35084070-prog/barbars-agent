"""Разведка источников финансирования покупки снаряжения.

Печатает:
  * полный каталог «Магазина снаряжения» по всем наборам: цена в золоте/серебре, id;
  * сырой HTML вокруг кнопки «Купить» для первого товара — есть ли выбор валюты;
  * все ссылки со страницы товара и со страницы героя (поиск обмена валют).

Запуск: python tools\\probe_funding.py <ник> <пароль>
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
        gold = silver = 0
        for icon, num in re.findall(
            r"icons/(money_gold|money_silver)\.png\"[^>]*>\s*<span>([\d.,]+)</span>", chunk
        ):
            val = int(float(num.replace(",", ".").replace(" ", "")))
            if icon == "money_gold":
                gold = val
            else:
                silver = val
        out.append(
            {
                "name": name,
                "id": m.group(2),
                "level": level.group(1) if level else "?",
                "gold": str(gold),
                "silver": str(silver),
            }
        )
    return out


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    page = s.get("https://barbars.ru/login", timeout=25)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
    res = s.post(
        "https://barbars.ru/" + form.group(1).lstrip("/"),
        data={"login": nick, "password": password},
        timeout=25,
        headers={"Referer": page.url},
    )
    print("вход:", res.status_code, res.url)

    hero = s.get("https://barbars.ru/user", timeout=25)
    htext = text_of(hero.text)
    print("\n=== /user (деньги/ресурсы) ===")
    for m in re.finditer(r"(деньги|ресурсы|золото|серебро|железо|мифрил|бтл)[^|]{0,120}", htext, re.I):
        print(" ", m.group(0)[:160])
    exch = [
        (t, h)
        for t, h in re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', hero.text, re.S | re.I)
        if re.search(r"обмен|exchange|валю|gold|silver|мейн|exchange", t + " " + text_of(h), re.I)
    ]
    print("\n=== ссылки-кандидаты в обмен (на /user) ===")
    for h, t in exch:
        print(" ", h, "|", text_of(t)[:60])

    total_g = total_s = 0
    first_id = None
    for set_name in SETS:
        url = "https://barbars.ru/trade/auction/shop"
        if set_name:
            url += f"/0/{set_name}"
        r = s.get(url, timeout=25)
        items = parse_items(r.text)
        print(f"\n=== набор {set_name or 'берсерк'} ({len(items)}) ===")
        for it in items:
            print(
                f"  {it['name'][:30]:32} ур {it['level']:>3} id {it['id']:>9} "
                f"цена {it['gold']} зол / {it['silver']} сер"
            )
            total_g += int(it["gold"])
            total_s += int(it["silver"])
            if first_id is None:
                first_id = it["id"]
    print(f"\nИТОГО по одному комплекту каждого набора: {total_g} зол / {total_s} сер")

    if first_id:
        r = s.get(f"https://barbars.ru/trade/auction/shop/item/id/{first_id}", timeout=25)
        print("\n=== страница товара ===")
        idx = r.text.lower().find("купить")
        print(text_of(r.text)[:1200])
        if idx > 0:
            print("\n--- сырой HTML вокруг «Купить» ---")
            print(r.text[max(0, idx - 1200) : idx + 1500])
        print("\n--- ссылки страницы товара ---")
        for h, t in re.findall(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r.text, re.S | re.I):
            print(" ", h, "|", text_of(t)[:60])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
