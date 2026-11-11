"""Ищет на странице героя возможность создать второго персонажа."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
game = Game(config, ROOT / config.get("profile_dir", "profile"))
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    for url in ("https://barbars.ru/user", "https://barbars.ru/"):
        game.goto(url)
        print(f"=== {url} ===")
        print("текст:", " ".join(game.body_text().split())[:700])
        for href, text in game.p.eval_on_selector_all(
            "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
        ):
            print(f"   {href}   | {text}")
        html = game.p.content()
        for pat in ("персонаж", "герой", "созда", "новый игрок", "сменить", "аккаунт", "пароль", "слот"):
            found = re.findall(rf"[^\"'<>]{{0,70}}{pat}[^\"'<>]{{0,70}}", html, re.IGNORECASE)
            if found:
                print(f"--- «{pat}»:")
                for item in list(dict.fromkeys(found))[:6]:
                    print("   ", " ".join(item.split())[:150])
finally:
    game.close()
