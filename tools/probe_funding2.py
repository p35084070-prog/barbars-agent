"""Точная проверка цен магазина снаряжения: валюта и точный размер.

Для каждого набора собирает список товаров со страницы списка, затем открывает
страницу каждого товара и вытаскивает:
  * текст ссылки «Купить за N»;
  * иконку валюты рядом с числом (money_gold / money_silver / money_...);
  * все иконки цен, встречающиеся в блоке покупки.

Запуск: python tools\\probe_funding2.py <ник> <пароль> [набор]
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


def list_items(html: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(
        r'<a[^>]*href="([^"]*shop/item/id/(\d+)[^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I
    ):
        name = " ".join(re.sub(r"<[^>]+>", " ", m.group(3)).split())
        if not name:
            continue
        out.append((m.group(2), name))
    seen = set()
    uniq = []
    for iid, name in out:
        if iid in seen:
            continue
        seen.add(iid)
        uniq.append((iid, name))
    return uniq


def price_of(html: str) -> str:
    """Текст и иконки валюты рядом с кнопкой «Купить»."""
    idx = html.find("buyoutLink")
    if idx < 0:
        idx = html.lower().find("купить")
    if idx < 0:
        return "(нет кнопки покупки)"
    frag = html[idx : idx + 1200]
    icons = re.findall(r"/images/icons/([a-z_]+\.png)", frag)
    nums = re.findall(r"<span>(\d+)</span>", frag)
    return f"текст={text_of(frag)[:60]!r} иконки={icons} числа={nums}"


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    only = sys.argv[3] if len(sys.argv) > 3 else None
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    page = s.get("https://barbars.ru/login", timeout=25)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
    s.post(
        "https://barbars.ru/" + form.group(1).lstrip("/"),
        data={"login": nick, "password": password},
        timeout=25,
        headers={"Referer": page.url},
    )
    for path in ("/payment/base", "/user/resources"):
        r = s.get("https://barbars.ru" + path, timeout=25)
        print(f"\n=== {path} :: {r.status_code} ===")
        print(text_of(r.text)[:1200])
    grand_g = grand_s = 0
    for set_name in SETS:
        if only and set_name != only:
            continue
        url = "https://barbars.ru/trade/auction/shop"
        if set_name:
            url += f"/0/{set_name}"
        r = s.get(url, timeout=25)
        items = list_items(r.text)
        print(f"\n=== набор {set_name or 'берсерк'} :: {len(items)} товаров ===")
        sg = ss = 0
        for iid, name in items:
            page_html = s.get(f"https://barbars.ru/trade/auction/shop/item/id/{iid}", timeout=25).text
            pr = price_of(page_html)
            g = re.search(r"money_gold\.png\"?[^>]*>\s*(?:<span>)?(\d+)", pr)
            sv = re.search(r"money_silver\.png\"?[^>]*>\s*(?:<span>)?(\d+)", pr)
            print(f"  {name[:30]:32} id {iid:>9} :: {pr}")
            if g:
                sg += int(g.group(1))
            if sv:
                ss += int(sv.group(1))
        print(f"  --- ИТОГО набор: {sg} зол / {ss} сер")
        grand_g += sg
        grand_s += ss
    print(f"\nВСЕ НАБОРЫ (по одному комплекту каждого): {grand_g} зол / {grand_s} сер")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
