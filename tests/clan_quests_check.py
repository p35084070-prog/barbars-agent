"""Диагностика: клановые задания и активный квест нового героя."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

GUILD = "16675"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    page = s.get(f"https://barbars.ru/guild/quests/0/{GUILD}", timeout=30)
    text = text_of(page.text)
    print("=== страница клановых заданий ===")
    print("\n".join(text.split("\n")[:70]))
    print("=== ссылки ===")
    for href in sorted(set(re.findall(r'href="([^"]+)"', page.text))):
        if "quest" in href.lower() or "task" in href.lower():
            print("  ", href)
    return 0


if __name__ == "__main__":
    sys.exit(main())
