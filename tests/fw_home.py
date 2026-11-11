"""После дневной награды: какие бесплатные бои открылись и где они."""
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


def main() -> int:
    s = login()
    home = s.get("https://barbars.ru/", timeout=30)
    (OUT / "home2.html").write_text(home.text, encoding="utf-8")
    print("--- текст главной ---")
    print(text_of(home.text))
    print("--- ссылки ---")
    for href in sorted(set(re.findall(r'href="([^"]+)"', home.text))):
        if "style.css" not in href:
            print(href)
    return 0


if __name__ == "__main__":
    sys.exit(main())
