"""Цены на бутылочки и стоимость аренды лота."""

import json
import re
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
        game.goto("https://barbars.ru/trade/bazaar")
        game.click_href("filterPotionsLink")
        text = game.body_text()
        print("=== БУТЫЛОЧКИ ===")
        print(text[:900])
        print("=== HTML фрагмент лота ===")
        html = game.p.content()
        m = re.search(r"Цена аренды лота.{0,200}", text, re.DOTALL)
        print(m.group(0) if m else "не найдено в тексте")
        rows = re.findall(r"(\d[\d\s]*)\s*бтл\s*(\d+)", text)
        print("пары (количество, цена):", rows[:12])
        gold_rows = re.findall(r"(\d[\d\s]*)\s*жлз\s*(\d+)", text)
        print("железо (количество, цена):", gold_rows[:6])
finally:
    game.close()
