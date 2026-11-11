"""Проверка пожертвования в алтарь: бонус до и после."""

import json
from pathlib import Path

from barbars.driver import Game
from barbars import pages

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(Path(__file__).resolve().parents[1])
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile-test")
game.start(headless=False)
try:
    if not game.ensure_login(timeout_sec=120):
        print("НЕ УДАЛОСЬ ВОЙТИ")
    else:
        game.goto("https://barbars.ru/guild/altar/0/16675")
        before = pages.altar_info(game)
        print("ДО:", before)
        result = game.activate_altar(resource="iron", amount=1250)
        print("РЕЗУЛЬТАТ:", result)
        game.goto("https://barbars.ru/guild/altar/0/16675")
        after = pages.altar_info(game)
        print("ПОСЛЕ:", after)
        st = game.status()
        print("ресурсы:", st.as_dict())
finally:
    game.close()
