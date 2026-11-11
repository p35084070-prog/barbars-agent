"""Быстрая проверка состояния обоих героев прямо в игре (без браузера)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")
ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path(r"C:\Users\Богдан\Desktop")


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    return "\n".join(l.strip() for l in t.splitlines() if l.strip())


def login(nick: str, password: str) -> requests.Session:
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
    data.update(login=nick, password=password)
    res = s.post("https://barbars.ru/" + action.lstrip("/"), data=data, timeout=30,
                 headers={"Referer": p.url})
    if "Вход для игроков" in text_of(res.text):
        raise SystemExit(f"вход не удался: {nick}")
    return s


def report(label: str, nick: str, password: str) -> None:
    s = login(nick, password)
    hero = " ".join(text_of(s.get("https://barbars.ru/user", timeout=30).text).split())
    res = " ".join(text_of(s.get("https://barbars.ru/user/resources", timeout=30).text).split())
    lvl = re.search(r"(\d+)\s*ур,\s*(воин|медик)", hero)
    exp = re.search(r"опыт:\s*([\d.,]+[kKmMgG]?)\s*/\s*([\d.,]+[kKmMgG]?)", hero)
    iron = re.search(r"Железо:\s*([\d,]+)", res)
    mif = re.search(r"Мифрил:\s*([\d,]+)", res)
    bot = re.search(r"Бутылочки:\s*([\d,]+)", res)
    print(f"{label}: ур={lvl.group(1) if lvl else '?'} {lvl.group(2) if lvl else ''} "
          f"опыт={exp.group(1) + '/' + exp.group(2) if exp else '?'} "
          f"железо={iron.group(1) if iron else '?'} "
          f"мифрил={mif.group(1) if mif else '?'} "
          f"бутылки={bot.group(1) if bot else '?'}")


def main() -> int:
    for label, filename in (("keis", "barbars-agentcredentials.txt"),
                            ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / filename).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        try:
            report(label, lines[0], lines[1])
        except SystemExit as exc:
            print(f"{label}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
