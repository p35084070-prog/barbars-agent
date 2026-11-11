"""Живая проверка входа в бой: клановый босс (два шага) и замок."""
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
    game = Game(config, profile_dir="probe-keis2")
    game.start()
    if not game.auto_login():
        print("вход не удался")
        return 1
    try:
        for label, url in (
            ("клановый босс", "https://barbars.ru/game/dragonDungeon"),
            ("замок", "https://barbars.ru/castle/6"),
        ):
            res = game.enter_activity(url, wait_sec=60)
            print(f"{label}: ok={res.get('ok')} stage={res.get('stage')!r} note={res.get('note')!r}")
            if res.get("ok"):
                print("   has_attack:", game.has_attack())
                game.click_text("Покинуть бой")
    finally:
        game.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
