"""Исследование торговли: профессии, магазины, аукционы, колодец удачи."""

import json
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(Path(__file__).resolve().parents[1])
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile-test")
game.start(headless=False)

PAGES = [
    ("ПРОФЕССИИ", "https://barbars.ru/trade/professions"),
    ("МАГАЗИНЫ", "https://barbars.ru/trade"),
    ("АУКЦИОНЫ", "https://barbars.ru/trade/auctions"),
    ("КОЛОДЕЦ", "https://barbars.ru/trade/well"),
    ("ЛАВКА МАСТЕРОВ", "https://barbars.ru/trade/masters"),
]

try:
    if not game.ensure_login(timeout_sec=120):
        print("НЕ УДАЛОСЬ ВОЙТИ")
    else:
        for title, url in PAGES:
            print("=" * 20, title, "=" * 20)
            try:
                game.goto(url)
            except Exception as exc:
                print("ошибка перехода:", exc)
                continue
            text = game.body_text()
            print(text[:1200])
            print("--- LINKS (первые 25) ---")
            for a in game.p.locator("a").all()[:25]:
                label = (a.inner_text() or "").strip().replace("\n", " ")
                href = (a.get_attribute("href") or "")[:70]
                if label:
                    print(repr(label), "|", href)
            print("--- FORMS ---")
            for f in game.p.locator("form").all():
                print("action:", f.get_attribute("action"))
            for i in game.p.locator("input").all():
                print("input:", i.get_attribute("type"), i.get_attribute("name"), repr(i.get_attribute("value")))
            print()
finally:
    game.close()
