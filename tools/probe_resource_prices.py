"""Проба «Аукциона ресурсов»: цены на железо, мифрил, бутылочки.

Нужно, чтобы понять, сколько серебра можно выручить продажей ресурсов
(серебро требуется на покупку снаряжения 25 уровня).

Запуск: python tools\\probe_resource_prices.py <ник> <пароль>
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
    for path in ("/trade/bazaar", "/trade/bazaar/0/1"):
        r = session.get("https://barbars.ru" + path, timeout=25)
        print(f"\n=== {path} :: {r.status_code} {r.url}")
        for resource in ("iron", "mifril", "bottles"):
            lots = pages.parse_lots(r.text, resource)
            if not lots:
                continue
            best = sorted(lots, key=lambda l: l["price_silver"])[:6]
            print(f"  -- {resource}: {len(lots)} лотов, самые дешёвые:")
            for lot in best:
                per = lot["price_silver"] / max(1, lot["amount"])
                print(
                    f"     {lot['amount']:>8} шт за {lot['gold']} зол {lot['silver']} сер "
                    f"({per:.3f} сер/шт)"
                )
        if not any(pages.parse_lots(r.text, res2) for res2 in ("iron", "mifril", "bottles")):
            print("  текст:", text_of(r.text)[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
