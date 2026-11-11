"""Проверка формата строки бонуса алтаря (TTL)."""

import json
import re
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
    game.ensure_guild_id()
    game.goto(f"https://barbars.ru/guild/altar/0/{game.guild_id}")
    text = game.body_text()
    for line in text.splitlines():
        if "бонус" in line.lower() or "ч" in line and "мин" in line:
            print(repr(line))
    m = re.search(r"Твой бонус:.{0,80}", text, re.S)
    print("ФРАГМЕНТ:", repr(m.group(0)) if m else "не найдено")
    from barbars import pages

    print("altar_info:", pages.altar_info(game))
finally:
    game.close()
