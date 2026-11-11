"""Отладка страницы талантов: структура строки и результат клика."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=False)
try:
    game.goto("https://barbars.ru/user/stances")
    print("=== POINTS ===")
    print([line for line in game.body_text().splitlines() if "очков" in line])
    print("=== TALENT LINKS ===")
    for a in game.p.locator("a").all():
        text = (a.inner_text() or "").strip()
        href = a.get_attribute("href") or ""
        if "stances" in href or text in {"+", "изучено"} or "talent" in href:
            print(repr(text), "|", href)
    print("=== ROW HTML (Лечебная поддержка) ===")
    row = game.p.locator("tr").filter(has_text="Лечебная поддержка").first
    print(row.inner_html()[:2000])
    print("=== CLICK FIRST + IN ROW ===")
    plus = row.locator("a").all()
    for i, a in enumerate(plus):
        print(i, repr(a.inner_text()), "|", a.get_attribute("href"))
    if plus:
        plus[-1].click()
        game._settle()
        print("=== AFTER CLICK ===")
        print([line for line in game.body_text().splitlines() if "очков" in line or "Лечебная" in line])
finally:
    game.close()
