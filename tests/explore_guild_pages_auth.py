"""Ищем каталог кланов (авторизованная сессия keis)."""
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
    for url in (
        "https://barbars.ru/guild/search",
        "https://barbars.ru/rating/guild",
        "https://barbars.ru/guild/list",
        "https://barbars.ru/users/search?type=guild",
    ):
        game.goto(url)
        print(f"=== {url} -> {game.p.url}")
        print("текст:", " ".join(game.body_text().split())[:400])
        html = game.p.content()
        for href, text in game.p.eval_on_selector_all(
            "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
        ):
            if text and ("guild" in (href or "").lower() or "клан" in text.lower()):
                print(f"   {href}   | {text}")
        for item in re.findall(r"[^\"'<>]{0,60}(?:вступи|Приглаш|приглаш)[^\"'<>]{0,60}", html, re.I):
            print("    html:", " ".join(item.split())[:140])
finally:
    game.close()
