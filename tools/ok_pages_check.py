"""Проверка доступности страниц всех модулей агента в канале ОК.

Открывает игру через ОК и обходит страницы, которые используют модули
(снаряжение, магазин, аукцион, рынок, умения, фарм-ивенты, почта...).

Запуск:
    python tools\ok_pages_check.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from barbars.ok_channel import OkGame  # noqa: E402

PAGES = [
    "/",
    "/user/stances",
    "/user/rack",
    "/user/store",
    "/user/public/store",
    "/user/master",
    "/user/mail",
    "/trade/bazaar",
    "/trade/auction",
    "/trade/auctions",
    "/trade/auction/shop",
    "/trade/well",
    "/trade/ironmaster",
    "/game/towers",
    "/game/bg",
    "/game/arena",
    "/game/contests",
    "/game/survival",
    "/game/dungeons",
    "/games/greats",
    "/castle/6",
    "/castle/8",
    "/game/battle",
    "/game/dragonDungeon",
    "/game/greatBoss",
]

BAD = ("Вход для игроков", "Страница не найдена", "Ошибка", "Нет прав", "Access denied")


def main() -> int:
    config = json.loads((ROOT / "config-ok.json").read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = OkGame(config, ROOT / "profile-ok-navtest")
    try:
        game.start(headless=True)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ игра не открылась: {exc}")
        return 1

    ok = 0
    for path in PAGES:
        started = time.time()
        good = game.goto_frame(game._to_ok_host(path))
        try:
            text = game.body_text()
        except Exception as exc:  # noqa: BLE001
            text = f"<ошибка чтения: {exc}>"
        flat = " ".join(text.split())
        bad = [b for b in BAD if b in flat]
        # страница считается рабочей, если это не заглушка входа/ошибки
        flag = "✅" if good and not bad and len(flat) > 30 else "⚠️ "
        if flag == "✅":
            ok += 1
        print(f"{flag} {path:26} ({time.time() - started:4.1f} c) {flat[:95]}")
    print(f"\nитого доступно: {ok}/{len(PAGES)}")
    game.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
