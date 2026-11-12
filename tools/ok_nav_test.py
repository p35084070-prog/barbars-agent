"""Проверка навигации по игре через канал ОК.

Открывает игру сессией из state/ok-session.b64 (или OK_SESSION_B64) и ходит
по страницам, которые использует агент: абсолютным https://barbars.ru/...,
корне-относительным (user/stances) и ссылкам из HTML.

Запуск:
    python tools\ok_nav_test.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from barbars.ok_channel import OkGame  # noqa: E402

PAGES = [
    "https://barbars.ru/",
    "user/stances",
    "https://barbars.ru/user/talent",
    "https://barbars.ru/game/towers",
    "https://barbars.ru/trade/well",
    "https://barbars.ru/user/rack",
    "https://barbars.ru/user/body/id/91889626630",
]


def main() -> int:
    config = json.loads((ROOT / "config-ok.json").read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = OkGame(config, ROOT / "profile-ok-navtest")
    try:
        game.start(headless=True)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ не удалось открыть игру через ОК: {exc}")
        return 1

    print(f"кадр: {game.current_url()}")
    print(f"jsessionid: {game.jsessionid}")
    ok = 0
    for path in PAGES:
        started = time.time()
        good = game.goto_frame(game._to_ok_host(path))
        took = time.time() - started
        try:
            text = game.body_text()
        except Exception as exc:  # noqa: BLE001
            text = f"<ошибка чтения: {exc}>"
        head = " ".join(text.split())[:110]
        flag = "✅" if good and "Вход для игроков" not in text else "❌"
        if flag == "✅":
            ok += 1
        print(f"{flag} {path} -> {game.current_url()} ({took:.1f} c) | {head}")
    print(f"\nитого: {ok}/{len(PAGES)} страниц открылось")
    game.close()
    return 0 if ok == len(PAGES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
