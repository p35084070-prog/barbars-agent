"""Проба «Аукциона вещей» и вкладок аукциона ресурсов.

Печатает:
  * лоты аукциона вещей (/trade/auctions → «Аукцион вещей») с ценами;
  * лучшие цены на мифрил и бутылочки (нужно, чтобы выручить серебро
    на покупку снаряжения).

Запуск: python tools\\probe_auction_items.py <ник> <пароль>
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

    # хаб аукционов → вкладка «Аукцион вещей»
    r = session.get("https://barbars.ru/trade/auctions", timeout=25)
    print("хаб аукционов:", r.status_code, r.url, len(r.text))
    print("  текст:", text_of(r.text)[:400])
    m = re.search(r'href="([^"]*auction[^"]*)"', r.text, re.I)
    if m:
        r2 = session.get("https://barbars.ru/" + m.group(1).lstrip("/"), timeout=25,
                         headers={"Referer": r.url})
        print("вкладка:", r2.status_code, r2.url, len(r2.text))
        lots = pages.parse_auction_items(r2.text)
        print(f"  лотов аукциона вещей: {len(lots)}")
        for lot in lots[:40]:
            print(
                f"   {lot['name'][:32]:34} ур {lot['level']:>3} тир {lot['tier'][:9]:10} "
                f"{lot['gold']} зол {lot['silver']} сер id={lot['item_id']}"
            )
        if not lots:
            print("  текст вкладки:", text_of(r2.text)[:400])

    # ресурсы: мифрил и бутылочки
    r3 = session.get("https://barbars.ru/trade/bazaar", timeout=25)
    for filt in ("filterMifrilLink", "filterPotionsLink", "filterIronLink"):
        if filt in r3.text:
            m2 = re.search(rf'href="([^"]*{filt}[^"]*)"', r3.text)
            if m2:
                r4 = session.get("https://barbars.ru/" + m2.group(1).lstrip("/"), timeout=25,
                                 headers={"Referer": r3.url})
                print(f"\n=== фильтр {filt} :: {r4.status_code} {r4.url}")
                for res_name, icon_key in (("mifril", "mifril"), ("bottles", "bottles"),
                                           ("iron", "iron")):
                    rl = pages.parse_lots(r4.text, res_name)
                    if not rl:
                        continue
                    best = sorted(rl, key=lambda l: l["price_silver"])[:5]
                    print(f"  -- {res_name}: {len(rl)} лотов")
                    for lot in best:
                        per = lot["price_silver"] / max(1, lot["amount"])
                        print(
                            f"     {lot['amount']:>8} шт за {lot['gold']} зол {lot['silver']} сер "
                            f"({per:.3f} сер/шт)"
                        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
