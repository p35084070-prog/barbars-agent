"""Дымовой тест драйвера на живой игре (без авторизации)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars.driver import Game  # noqa: E402

config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(config, Path(__file__).resolve().parents[1] / "profile-smoke")
game.start(headless=True)
try:
    game.goto("https://barbars.ru/help/0/games")
    text = game.body_text()
    print("help page ok, символов:", len(text), "| заголовок:", game.p.title())
    print("ссылок:", len(game.link_texts()))

    game.goto("https://barbars.ru/")
    body = game.body_text()
    logged_in = "Выход" in body
    print("главная ok, авторизован:", logged_in)
    print("статусы:", game.status().as_dict())
    hero = game.hero()
    print("герой:", vars(hero))
    print("цели:", [vars(t) for t in __import__("barbars.pages", fromlist=["x"]).home_targets(game)])
    print("лимиты боёв:", game.fight_limits())
finally:
    game.close()
print("smoke ok")
