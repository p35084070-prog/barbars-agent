"""Полный разбор результатов поиска игрока (ищем кнопку приглашения в клан)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

NICK = sys.argv[1] if len(sys.argv) > 1 else "fire white ii"

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
game = Game(config, ROOT / config.get("profile_dir", "profile"))
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    game.goto("https://barbars.ru/users/search")
    game.p.fill("input[name='name']", NICK, timeout=8000)
    game.p.click("input[type='submit']")
    game._settle()
    html = game.p.content()
    print("текст:", " ".join(game.body_text().split())[:400])
    print("=== все ссылки")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,60)])"
    ):
        print(f"   {href}   | {text}")
    print("=== input/button")
    for tag in re.findall(r"<(?:input|button)[^>]*>", html, re.I):
        print("   ", " ".join(tag.split()))
    for item in re.findall(r"[^\"'<>]{0,70}(?:invite|Приглаш|приглаш)[^\"'<>]{0,70}", html, re.I):
        print("    html:", " ".join(item.split())[:160])
finally:
    game.close()
