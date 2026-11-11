"""Живая проверка: открывает башню для keis и ищет кнопку атаки."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402


def main() -> int:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    config["headless"] = True
    game = Game(config, profile_dir="probe-keis")
    game.start()
    if not game.auto_login():
        print("вход не удался")
        return 1
    try:
        name = game.open_tower()
        print("локация:", name)
        print("has_attack:", game.has_attack())
        print("has_combat_button:", game.has_combat_button())
        print("текст:", " ".join(game.body_text().split())[:400])
    finally:
        game.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
