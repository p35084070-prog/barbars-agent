"""Где игра держит купленные вещи: разбор HTML главной и рюкзака.

Печатает все ссылки с item/id и ссылки перемещения (в рюкзак/на витрину)
со страниц /user, /user/rack, /user/store, /user/public/store.

Запуск: python tools\\probe_new_items.py <ник> <пароль>
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
    for path in (
        "/",
        "/trade/auction/shop",
        "/trade/auction/shop/item/id/40121857",
        "/user",
    ):
        r = s.get("https://barbars.ru" + path, timeout=25)
        print(f"\n================ {path} :: {r.status_code}")
        text = text_of(r.text)
        print("текст:", text[:700])
        print("--- ссылки item/id и перемещения:")
        for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S | re.I):
            href, label = m.group(1), " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
            if re.search(r"item/id|toRack|toStore|wearLink|newItem|рюкзак", href + " " + label, re.I):
                print(f"   {label[:40]:42} {href[:110]}")
        for m in re.finditer(r'items:(\d+):(\w+)', r.text):
            pass
        links = sorted(set(re.findall(r"items:\d+:\w+", r.text)))
        print("--- item-action ссылки:", links[:40])
    mail = s.get("https://barbars.ru/user/mail", timeout=25)
    print("\n================ ПОЧТА ================")
    print("текст:", text_of(mail.text)[:800])
    parcels = re.findall(r'href="(?:\.\./)*user/mail/message/id/(\d+)"', mail.text)
    print("посылки:", parcels[:20])
    if parcels:
        pid = parcels[0]
        page = s.get(f"https://barbars.ru/user/mail/message/id/{pid}", timeout=25)
        print(f"--- страница посылки {pid}: {page.status_code} {page.url}")
        print("текст:", text_of(page.text)[:900])
        print("--- все ссылки:")
        for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page.text, re.S | re.I):
            print(f"   {' '.join(re.sub('<[^>]+>', ' ', m.group(2)).split())[:45]:47} {m.group(1)[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
