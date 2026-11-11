"""Разведка страниц нового героя: опыт, ресурсы, бесплатные бои, задания."""
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
OUT.mkdir(parents=True, exist_ok=True)


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    return "\n".join(lines)


def login() -> requests.Session:
    creds = fw_auth.load()
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    p = s.get("https://barbars.ru/login", timeout=30)
    action = re.search(r'<form action="([^"]+)"[^>]*method="post"', p.text).group(1)
    data = {}
    for tag in re.findall(r"<input[^>]*>", p.text):
        name = re.search(r'name="([^"]+)"', tag)
        val = re.search(r'value="([^"]*)"', tag)
        if name:
            data[name.group(1)] = val.group(1) if val else ""
    data["login"] = creds["nick"]
    data["password"] = creds["password"]
    url = "https://barbars.ru/" + action.lstrip("/")
    res = s.post(url, data=data, timeout=30, headers={"Referer": p.url})
    body = text_of(res.text)
    if "Вход для игроков" in body or not any(
        m in body for m in ("Мой герой", "Дуэли", "Задания", "Башня призраков")
    ):
        print(body[:400])
        raise SystemExit("вход не удался")
    print("вход ок:", creds["nick"])
    return s


PAGES = [
    ("home", "https://barbars.ru/"),
    ("hero", "https://barbars.ru/user"),
    ("resources", "https://barbars.ru/user/resources"),
    ("quests", "https://barbars.ru/user/quests"),
    ("dungeons", "https://barbars.ru/game/dungeons"),
    ("tower", "https://barbars.ru/game/towers"),
    ("journey", "https://barbars.ru/journey"),
    ("fightmore", "https://barbars.ru/fightmore"),
    ("ironmaster", "https://barbars.ru/trade/ironmaster"),
]


def main() -> int:
    s = login()
    for name, url in PAGES:
        try:
            r = s.get(url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            print(name, "ошибка", exc)
            continue
        t = text_of(r.text)
        (OUT / f"{name}.txt").write_text(t, encoding="utf-8")
        (OUT / f"{name}.html").write_text(r.text, encoding="utf-8")
        print("=" * 60)
        print(f"### {name} -> {r.status_code} {r.url}  ({len(t)} симв.)")
        print(t[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
