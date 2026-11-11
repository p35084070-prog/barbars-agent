"""Проверяет партнёрский вход barbars.ru через channelId=35 (каталог igrotop)."""
from __future__ import annotations

import re

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def show(label: str, resp: requests.Response) -> str:
    body = resp.text
    print(f"--- {label}: {resp.status_code} len={len(body)} url={resp.url}")
    print("    цепочка:", [(r.status_code, r.headers.get("location", "")[:110]) for r in resp.history])
    for href, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.IGNORECASE | re.DOTALL):
        clean = " ".join(re.sub(r"<[^>]+>", " ", text).split())
        print(f"    ссылка: {href} | {clean[:50]}")
    txt = re.sub(r"<script.*?</script>", " ", body, flags=re.IGNORECASE | re.DOTALL)
    txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.IGNORECASE | re.DOTALL)
    txt = re.sub(r"<[^>]+>", " ", txt)
    print("    текст:", " ".join(txt.split())[:400])
    return body


session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})

show("каталог", session.get("http://igrotop.mobi/go/game/1/", timeout=25))
body = show("partner root", session.get("https://barbars.ru/?channelId=35", timeout=25,
                                       headers={"Referer": "http://igrotop.mobi/"}))
show("registration", session.get("https://barbars.ru/registration", timeout=25))
show("start", session.get("https://barbars.ru/start", timeout=25))
