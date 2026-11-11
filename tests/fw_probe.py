"""Проба источников опыта/железа для нового героя: дневная награда, башня."""
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
    assert "Вход для игроков" not in text_of(res.text), "вход не удался"
    return s


def norm(s: str) -> str:
    table = str.maketrans({"B": "В", "C": "С", "H": "Н", "K": "К", "M": "М",
                           "T": "Т", "e": "е", "a": "а", "o": "о", "c": "с",
                           "p": "р", "x": "х", "y": "у"})
    return s.translate(table)


def state(s: requests.Session) -> dict:
    r = s.get("https://barbars.ru/user", timeout=30)
    t = norm(text_of(r.text))
    out = {}
    m = re.search(r"(\d+)\s*ур", t)
    out["level"] = int(m.group(1)) if m else None
    m = re.search(r"опыт:\s*([\d,\.]+)\s*/\s*([\d,\.]+)", t)
    if m:
        out["exp"] = m.group(1)
        out["exp_next"] = m.group(2)
    r2 = s.get("https://barbars.ru/user/resources", timeout=30)
    t2 = norm(text_of(r2.text))
    for key, pat in (("iron", r"Железо:\s*([\d,]+)"), ("mifril", r"Мифрил:\s*([\d,]+)"),
                     ("bottles", r"Бутылочки:\s*([\d,]+)")):
        m = re.search(pat, t2)
        out[key] = m.group(1) if m else None
    return out


def click(s: requests.Session, base: str, href: str) -> str:
    href = href.replace("&amp;", "&")
    if href.startswith("http"):
        url = href
    else:
        url = base.split("?")[0] + ("?" + href.split("?", 1)[1] if "?" in href else "")
    r = s.get(url, timeout=30, headers={"Referer": base})
    return r.text


def main() -> int:
    s = login()
    print("старт:", state(s))

    home = s.get("https://barbars.ru/", timeout=30)
    m = re.search(r'href="([^"]*awardLink[^"]*)"', home.text)
    if m:
        html = click(s, home.url, m.group(1))
        t = norm(text_of(html))
        print("награда:", " | ".join(t.split("\n")[6:26]))
    else:
        print("награда: ссылки нет")
    print("после награды:", state(s))

    towers = s.get("https://barbars.ru/game/towers", timeout=30)
    loc = re.findall(r'href="([^"]*locationLink[^"]*)"', towers.text)
    print("башня: локаций", len(loc))
    if loc:
        html = click(s, towers.url, loc[0])
        t = norm(text_of(html))
        print("башня страница:", " | ".join(t.split("\n")[:14]))
        m = re.search(r'href="([^"]+)"[^>]*>\s*Бить', html)
        print("есть кнопка бить:", bool(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
