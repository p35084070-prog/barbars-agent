"""Разбор страницы башни: ссылки, бой, что даёт (опыт/железо)."""
from __future__ import annotations

import json
import re
import sys
import time
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


def click(s: requests.Session, base: str, href: str) -> str:
    href = href.replace("&amp;", "&")
    url = href if href.startswith("http") else base.split("?")[0] + (
        "?" + href.split("?", 1)[1] if "?" in href else "")
    return s.get(url, timeout=30, headers={"Referer": base}).text


def main() -> int:
    s = login()
    towers = s.get("https://barbars.ru/game/towers", timeout=30)
    loc = re.findall(r'href="([^"]*locationLink[^"]*)"', towers.text)
    html = click(s, towers.url, loc[0])
    (OUT / "tower-fight.html").write_text(html, encoding="utf-8")
    print("текст:", " | ".join(text_of(html).split("\n")[:20]))
    print("ссылки:")
    for h in sorted(set(re.findall(r'href="([^"]+)"', html))):
        if "style.css" not in h:
            print("  ", h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
