"""Полный текст страницы Мудреца (trade/ironmaster) в канале ОК.

Нужно, чтобы понять, какие варианты покупки опыта есть: за железо
(как ждёт агент) или за золото.

Запуск:
    python tools\ok_sage_dump.py
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

    game.goto("https://barbars.ru/trade/ironmaster")
    print("===== ПОЛНЫЙ ТЕКСТ МУДРЕЦА =====")
    for line in game.body_text().splitlines():
        if line.strip():
            print(f"  {line.strip()!r}")

    print("\n===== ВСЕ ССЫЛКИ С «Пожертвовать» =====")
    for link in game.p.locator("a").all():
        try:
            text = (link.inner_text() or "").strip().replace("\n", " ")
            href = (link.get_attribute("href") or "")[:130]
        except Exception:
            continue
        if "ожертв" in text or "олить" in text or "опыт" in text.lower():
            print(f"  {text!r}\n      -> {href!r}")

    game.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
