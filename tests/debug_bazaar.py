"""Исследование аукциона ресурсов и мастера-мудреца (опыт за железо)."""

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
        for title, url in [
            ("АУКЦИОН РЕСУРСОВ", "https://barbars.ru/trade/bazaar"),
            ("МУДРЕЦ (опыт)", "https://barbars.ru/trade/ironmaster"),
            ("РЮКЗАК", "https://barbars.ru/user/rack"),
        ]:
            print("=" * 20, title, "=" * 20)
            game.goto(url)
            print(game.body_text()[:1400])
            print("--- LINKS ---")
            for a in game.p.locator("a").all()[:30]:
                label = (a.inner_text() or "").strip().replace("\n", " ")
                href = (a.get_attribute("href") or "")[:75]
                if label:
                    print(repr(label), "|", href)
            print("--- INPUTS ---")
            for i in game.p.locator("input").all():
                print(i.get_attribute("type"), i.get_attribute("name"), repr(i.get_attribute("value")))
            print()
finally:
    game.close()
