"""Живая проверка выставления лота на аукционе ресурсов.

Выставляет маленький лот бутылочек по рыночной цене (100 бтл за 2 зол 50 сер)
и смотрит, как он выглядит во вкладке «Мои лоты» (есть ли снятие лота).
"""

import json
from pathlib import Path

from barbars.driver import Game

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(ROOT)
game = Game(cfg, ROOT / "profile-test")
game.start(headless=False)
try:
    if not game.ensure_login(timeout_sec=180):
        print("НЕ УДАЛОСЬ ВОЙТИ")
        raise SystemExit(1)

    result = game.sell_resource("bottles", 100, 2, 50)
    print("выставление:", result)

    print("=== МОИ ЛОТЫ ===")
    game.goto("https://barbars.ru/trade/bazaar")
    game.click_href("filterMyLotsLink")
    text = game.body_text()
    print(text[:1500])
finally:
    game.close()
