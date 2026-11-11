"""Настройки нового героя: ищем «Хочу в клан»."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

config = json.loads((ROOT / "config-firewhite.json").read_text(encoding="utf-8"))
config["_root"] = str(ROOT)
game = Game(config, ROOT / "profile-firewhite")
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    game.goto("https://barbars.ru/user/settings")
    print("текст:", " ".join(game.body_text().split())[:900])
    html = game.p.content()
    print("=== ссылки")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,50)])"
    ):
        print(f"   {href}   | {text}")
    print("=== input/button")
    for tag in re.findall(r"<(?:input|button)[^>]*>", html, re.I):
        print("   ", " ".join(tag.split())[:180])
    for item in re.findall(r"[^\"'<>]{0,70}(?:клан|guild)[^\"'<>]{0,70}", html, re.I):
        print("    html:", " ".join(item.split())[:160])
finally:
    game.close()
