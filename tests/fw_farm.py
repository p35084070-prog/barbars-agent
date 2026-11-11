"""Замер: что даёт бой на башне (опыт, железо, бутылки) для нового героя."""
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
    assert "Вход для игроков" not in text_of(res.text)
    return s


def state(s: requests.Session) -> str:
    r = s.get("https://barbars.ru/user", timeout=30)
    t = " ".join(text_of(r.text).split())
    m = re.search(r"опыт:\s*([\d,\.]+)\s*/\s*([\d,\.]+)", t)
    exp = m.group(1) + "/" + m.group(2) if m else "?"
    r2 = s.get("https://barbars.ru/user/resources", timeout=30)
    t2 = " ".join(text_of(r2.text).split())
    iron = re.search(r"Железо:\s*([\d,]+)", t2)
    bot = re.search(r"Бутылочки:\s*([\d,]+)", t2)
    mif = re.search(r"Мифрил:\s*([\d,]+)", t2)
    return (f"опыт={exp} железо={iron.group(1) if iron else '?'} "
            f"бутылки={bot.group(1) if bot else '?'} мифрил={mif.group(1) if mif else '?'}")


def click(s: requests.Session, base: str, href: str) -> str:
    href = href.replace("&amp;", "&")
    url = href if href.startswith("http") else base.split("?")[0] + (
        "?" + href.split("?", 1)[1] if "?" in href else "")
    return s.get(url, timeout=30, headers={"Referer": base}).text


def main() -> int:
    s = login()
    print("старт:", state(s))
    towers = s.get("https://barbars.ru/game/towers", timeout=30)
    loc = re.findall(r'href="([^"]*locationLink[^"]*)"', towers.text)
    html = click(s, towers.url, loc[0])
    for i in range(14):
        t = " | ".join(text_of(html).split("\n")[:8])
        print(f"[{i}] {t[:220]}")
        m = re.search(r'href="([^"]*damageRandomEnemyLink[^"]*)"', html)
        if not m:
            m = re.search(r'href="([^"]*ability:0:activateLink[^"]*)"', html)
        if not m:
            print("  нет ссылки удара")
            break
        time.sleep(0.6)
        html = click(s, "https://barbars.ru/game/towers", m.group(1))
        if i % 4 == 3:
            print("   состояние:", state(s))
    print("итог:", state(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
