"""Отладка: какие умения и действия доступны медику."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=False)
try:
    game.goto("https://barbars.ru/user/abilities/0/905853")
    print("=== ABILITIES ===")
    print(game.body_text()[:1500])
    print("=== ABILITY LINKS ===")
    for a in game.p.locator("a").all()[:16]:
        print(repr((a.inner_text() or "").strip()), "|", (a.get_attribute("href") or "")[:70])

    game.goto("https://barbars.ru/game/duel")
    print("=== DUEL PAGE ===")
    print(game.body_text()[:1200])
    print("=== DUEL LINKS ===")
    for a in game.p.locator("a").all()[:16]:
        print(repr((a.inner_text() or "").strip()), "|", (a.get_attribute("href") or "")[:70])
finally:
    game.close()
