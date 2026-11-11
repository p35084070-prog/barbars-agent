"""Отладка формы входа: поля и кнопка отправки."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile-smoke")
game.start(headless=True)
try:
    game.goto("https://barbars.ru/")
    print("=== TEXT ===")
    print(game.body_text()[:600])
    print(">>> переходим на форму входа")
    game.click_href("login")
    print("URL:", game.p.url)
    print("=== TEXT ===")
    print(game.body_text()[:600])
    print("=== INPUTS ===")
    for i in game.p.locator("input").all():
        print("type:", i.get_attribute("type"), "| name:", i.get_attribute("name"), "| id:", i.get_attribute("id"), "| value:", i.get_attribute("value"))
    print("=== BUTTONS ===")
    for b in game.p.locator("button, input[type=submit], a").all():
        text = (b.inner_text() or b.get_attribute("value") or "").strip()
        if text:
            print(repr(text), "|", b.get_attribute("name"), "|", b.get_attribute("id"))
    print("=== FORMS ===")
    for f in game.p.locator("form").all():
        print("action:", f.get_attribute("action"), "| method:", f.get_attribute("method"))
finally:
    game.close()
