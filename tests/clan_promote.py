"""Повышает героя в клане до генерала (делает это лидер — keis).

Запуск:
  python tests\\clan_promote.py --member "Fire White" --target генерал
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

RANKS = ["рядовой", "офицер", "генерал", "маршал", "лидер"]


def member_block(page, member: str) -> str:
    """Возвращает HTML блока участника с указанным ником."""
    html = page.content()
    idx = html.find(member)
    if idx < 0:
        return ""
    left = max(0, idx - 1200)
    return html[left : idx + 1200]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member", default="Fire White")
    parser.add_argument("--target", default="генерал")
    parser.add_argument("--guild", default="16675")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = Game(config, ROOT / config.get("profile_dir", "profile"))
    game.start(headless=True)
    try:
        if not game.ensure_login(timeout_sec=180):
            print("НЕ УДАЛОСЬ войти под лидером")
            return 1
        for step in range(4):
            game.goto(f"https://barbars.ru/guild/{args.guild}")
            game.click_text("Управление кланом", tags=("a", "span", "div"))
            html = game.p.content()
            idx = html.find(args.member)
            if idx < 0:
                print("участник не найден в списке")
                return 2
            block = html[max(0, idx - 1500) : idx + 1500]
            rank = None
            for r in RANKS:
                if re.search(rf">{re.escape(r)}\s*<", block) or f">{r} " in block:
                    rank = r
                    break
            print(f"шаг {step}: текущий ранг — {rank}")
            if rank == args.target:
                print("нужный ранг уже есть")
                return 0
            promoted = False
            for candidate in ("повысить", "Передать лидера", "передать лидера"):
                locator = game.p.locator("a:has-text('" + candidate + "')")
                count = locator.count()
                for i in range(count):
                    link = locator.nth(i)
                    href = link.get_attribute("href") or ""
                    # берём только кнопку из блока нужного участника
                    if "promoteLink" in href or candidate != "повысить":
                        try:
                            link.click(timeout=8000)
                            game._settle()
                            promoted = True
                            print(f"   нажато «{candidate}» ({href[:80]})")
                            break
                        except Exception as exc:  # noqa: BLE001
                            print("   клик не удался:", exc)
                if promoted:
                    break
            if not promoted:
                print("кнопка повышения не найдена")
                return 3
            game.p.wait_for_timeout(800)
        print("готово")
        return 0
    finally:
        game.close()


if __name__ == "__main__":
    sys.exit(main())
