"""Проверка входа нового героя и сохранение сессии."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def main() -> int:
    creds = json.loads((ROOT / "credentials-firewhite.json").read_text(encoding="utf-8"))
    for nick in {creds["nick"], creds["nick"].lower(), creds["nick"].title()}:
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
        page = session.get("https://barbars.ru/login", timeout=30)
        form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
        res = session.post("https://barbars.ru/" + form.group(1).lstrip("/"),
                           data={"login": nick, "password": creds["password"]},
                           timeout=30, headers={"Referer": page.url})
        body = text_of(res.text)
        ok = "Выход" in body or "Мой герой" in body
        print(f"вход как «{nick}»: {'ОК' if ok else 'не удалось'} :: {body[:150]}")
        if ok:
            hero = session.get("https://barbars.ru/user", timeout=30)
            print("герой:", text_of(hero.text)[:200])
            (ROOT / "knowledge" / "discovered" / "firewhite-login.json").write_text(
                json.dumps({c.name: c.value for c in session.cookies}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            creds["nick"] = nick
            (ROOT / "credentials-firewhite.json").write_text(
                json.dumps(creds, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("вход подтверждён, ник:", nick)
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
