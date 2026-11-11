"""Отладка страницы алтаря клана: как активировать и сколько это стоит."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(Path(__file__).resolve().parents[1])
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile-test")
game.start(headless=False)
try:
    if not game.ensure_login(timeout_sec=120):
        print("НЕ УДАЛОСЬ ВОЙТИ")
    else:
        game.goto("https://barbars.ru/guild/altar/0/16675")
        print("=== TEXT ===")
        print(game.body_text()[:1500])
        print("=== LINKS ===")
        for a in game.p.locator("a").all():
            text = (a.inner_text() or "").strip().replace("\n", " ")
            if text:
                print(repr(text), "|", (a.get_attribute("href") or "")[:80])
        print("=== BUTTONS/INPUTS ===")
        for b in game.p.locator("button, input").all():
            print(b.get_attribute("type"), repr(b.get_attribute("value")), "|", b.get_attribute("name"))
finally:
    game.close()
