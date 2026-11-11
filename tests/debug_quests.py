"""Отладка страницы клановых заданий: как выглядит взятое задание."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=False)
try:
    game.goto("https://barbars.ru/guild/quests/0/16675")
    print("=== TEXT ===")
    print(game.body_text()[:2500])
    print("=== LINKS (первые 20) ===")
    for a in game.p.locator("a").all()[:20]:
        print(repr((a.inner_text() or "").strip()), "|", (a.get_attribute("href") or "")[:60])
finally:
    game.close()
