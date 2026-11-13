"""Диагностика починки снаряжения и покупки железа в канале ОК.

Показывает: как определился hero_id, что видно на странице героя про
починку (с точными символами — игра местами подменяет кириллицу
латинскими «двойниками»), и есть ли на аукционе ресурсов лоты железа.

Запуск:
    python tools\ok_repair_diag.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from barbars import pages  # noqa: E402
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

    game.goto("https://barbars.ru/")
    print(f"hero_id: {game.hero_id}")

    hero_id = game.hero_id or "91889626630"
    game.goto(f"https://barbars.ru/user/body/id/{hero_id}")
    text = game.body_text()
    print("\n--- строки со «очин» на странице героя ---")
    found = False
    for line in text.splitlines():
        if "очин" in line.lower() or "чин" in line.lower():
            found = True
            print(f"  {line.strip()[:120]!r}")
    if not found:
        print("  (строк с «очин» нет — кнопки починки на странице отсутствуют)")

    print("\n--- ссылки a/button, содержащие «очин» (в любом регистре) ---")
    hits = 0
    for tag in ("a", "button"):
        for link in game.p.locator(tag).all():
            try:
                t = (link.inner_text() or "").strip()
            except Exception:
                continue
            if "чин" in t.lower():
                hits += 1
                print(f"  {tag}: {t[:100]!r}")
    print(f"  всего: {hits}")

    print("\n--- pages.repair_info ---")
    print(" ", pages.repair_info(game))

    print("\n--- селектор Playwright a:has-text('Починить') ---")
    print("  count:", game.p.locator("a:has-text('Починить'), button:has-text('Починить')").count())

    print("\n--- аукцион ресурсов: лоты железа ---")
    game.goto("https://barbars.ru/trade/auction")
    lots = pages.parse_lots(game.p.content(), "iron")
    print(f"  лотов железа: {len(lots)}")
    for lot in lots[:5]:
        print("   ", lot)
    body = game.body_text()
    m = re.search(r"(желез[^\n]{0,60})", body, re.IGNORECASE)
    print("  текст про железо:", m.group(1) if m else "не найден")

    game.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
