"""Проверка аукциона ресурсов (железо за золото) в канале ОК.

Адрес /trade/bazaar в мобильной сборке игры может отсутствовать — тогда
купить железо за золото нельзя и золото тратится на опыт у мудреца.

Запуск:
    python tools\ok_iron_auction.py
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

    for path in ("https://barbars.ru/trade/bazaar", "https://barbars.ru/trade/auction"):
        game.goto(path)
        text = " ".join(game.body_text().split())
        print(f"\n== {path} ==")
        print(f"  первые слова: {text[:160]}")
        for marker in ("filterIronLink", "buyLink", "жлз", "Базар", "аукцион ресурсов"):
            print(f"  {marker}: {'есть' if marker in (game.p.content() or '') else 'нет'}")

    print("\n== iron_lots() ==")
    lots = game.iron_lots()
    print(f"  лотов: {len(lots)}")
    for lot in lots[:5]:
        print("   ", lot)

    game.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
