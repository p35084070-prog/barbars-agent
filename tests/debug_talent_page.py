"""Отладка страницы одного таланта: что нажимать, чтобы потратить очко."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=False)
try:
    game.goto("https://barbars.ru/user/talent/0/234")
    print("URL:", game.p.url)
    print("=== TEXT ===")
    print(game.body_text()[:1200])
    print("=== LINKS ===")
    for a in game.p.locator("a").all():
        print(repr((a.inner_text() or "").strip()), "|", a.get_attribute("href"))
    print("=== INPUTS ===")
    for i in game.p.locator("input").all():
        print(repr(i.get_attribute("type")), repr(i.get_attribute("value")), "|", i.get_attribute("name"))
finally:
    game.close()
