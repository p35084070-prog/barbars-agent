"""Ресурсы, рюкзак и авторазбор нового героя — сколько железа даёт разбор вещей."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

import fw_auth

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered" / "fw-pages"


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    return "\n".join(l.strip() for l in t.splitlines() if l.strip())


def login() -> requests.Session:
    creds = fw_auth.load()
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    p = s.get("https://barbars.ru/login", timeout=30)
    action = re.search(r'<form action="([^"]+)"[^>]*method="post"', p.text).group(1)
    data = {}
    for tag in re.findall(r"<input[^>]*>", p.text):
        n = re.search(r'name="([^"]+)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            data[n.group(1)] = v.group(1) if v else ""
    data.update(login=creds["nick"], password=creds["password"])
    res = s.post("https://barbars.ru/" + action.lstrip("/"), data=data, timeout=30,
                 headers={"Referer": p.url})
    assert "Вход для игроков" not in text_of(res.text)
    return s


def res_state(s: requests.Session) -> dict:
    r = s.get("https://barbars.ru/user/resources", timeout=30)
    t = " | ".join(text_of(r.text).split("\n"))
    return {"url": r.url, "text": t[:400]}


def main() -> int:
    s = login()
    print("ресурсы:", res_state(s))
    hero = s.get("https://barbars.ru/user", timeout=30)
    print("герой:", " | ".join(text_of(hero.text).split("\n")[:40]))
    # рюкзак
    m = re.search(r'href="([^"]*rack[^"]*)"', hero.text)
    print("ссылка рюкзака:", m.group(1) if m else None)
    if m:
        bag = s.get("https://barbars.ru/" + m.group(1).lstrip("/").split("?")[0], timeout=30)
        (OUT / "bag.html").write_text(bag.text, encoding="utf-8")
        print("рюкзак:", " | ".join(text_of(bag.text).split("\n")[:40]))
    # авторазбор
    ac = s.get("https://barbars.ru/user/rack/autocrack", timeout=30)
    (OUT / "autocrack-fw.html").write_text(ac.text, encoding="utf-8")
    print("авторазбор:", " | ".join(text_of(ac.text).split("\n")[:40]))
    print("ссылки разбора:", sorted(set(re.findall(r'href="([^"]*autoCrack[^"]*)"', ac.text))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
