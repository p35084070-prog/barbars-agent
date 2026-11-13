"""Текущие характеристики героя в канале ОК: HP, энергия, ресурсы.

Запуск:
    python tools\ok_hero_stats.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from barbars.ok_channel import OkGame  # noqa: E402


def main() -> int:
    config = json.loads((ROOT / "config-ok.json").read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = OkGame(config, ROOT / "profile-ok-navtest")
    try:
        game.start(headless=True)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ игра не открылась: {exc}")
        return 1

    print(f"hero_id: {game.hero_id}")
    for title, path in (("главная", "https://barbars.ru/"), ("герой", "https://barbars.ru/user")):
        game.goto(path)
        st = game.status()
        print(f"\n== {title} ==")
        print(f"  hp={st.hp} энергия={st.energy} золото={st.gold} серебро={st.silver} "
              f"железо={st.iron} мифрил={st.mifril} бутылки={st.bottles}")
        for line in game.body_text().splitlines():
            low = line.strip().lower()
            if low.startswith(("здоровье", "энергия", "опыт", "уровень", "профессия")):
                print(f"  {line.strip()!r}")

    game.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
