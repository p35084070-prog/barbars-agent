"""Кто заходит через ОК-канал: имя героя, баланс, что сломано в снаряжении."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars import pages  # noqa: E402
from barbars.ok_channel import OkGame  # noqa: E402


def main() -> int:
    config = json.loads((ROOT / "config-ok.json").read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = OkGame(config, ROOT / "profile-ok-who")
    try:
        game.start(headless=True)
    except Exception as exc:  # noqa: BLE001
        print(f"игра не открылась: {exc}")
        return 1
    try:
        if not game.ensure_login(timeout_sec=120):
            print("не удалось войти через ОК")
            return 1
        game.goto("https://barbars.ru/user")
        body = [l.strip() for l in game.body_text().splitlines() if l.strip()]
        print("=== страница героя ===")
        print("\n".join(body[:25]))
        hero = game.hero()
        print("\nгерой:", hero)
        print("hero_id:", game.hero_id, "| guild_id:", game.guild_id)
        st = game.status()
        print("баланс:", st)
        if game.hero_id:
            game.goto(f"https://barbars.ru/user/body/id/{game.hero_id}")
            print("\n=== снаряжение ===")
            print(pages.repair_info(game))
            b2 = [l.strip() for l in game.body_text().splitlines() if l.strip()]
            print("\n".join(b2[:40]))
    finally:
        try:
            game.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
