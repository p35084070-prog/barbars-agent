"""Живая проверка: порядок кликов для кланового босса."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402


def main() -> int:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config["headless"] = True
    game = Game(config, profile_dir="probe-keis3")
    game.start()
    if not game.auto_login():
        print("вход не удался")
        return 1
    try:
        game.goto("https://barbars.ru/game/dragonDungeon")
        print("readyLink есть:", game.p.locator("a[href*='readyLink']").count())
        print("startCombatLink есть:", game.p.locator("a[href*='startCombatLink']").count())
        print("клик «Я готов!»:", game.click_href("readyLink"))
        time.sleep(2)
        print("клик «Начать бой!»:", game.click_href("startCombatLink"))
        for i in range(12):
            time.sleep(6)
            print(f"  t+{6*(i+1)}с has_attack={game.has_attack()} has_combat={game.has_combat_button()}",
                  "|", " ".join(game.body_text().split())[:120])
            if game.has_attack():
                break
    finally:
        game.click_text("Покинуть бой")
        game.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
