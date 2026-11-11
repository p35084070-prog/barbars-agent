"""Проверка: второй герой в клане и его ранг (глазами лидера keis)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

GUILD = "16675"
NICK = "fire white ii"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    s.get(f"https://barbars.ru/guild/{GUILD}", timeout=30)
    page = s.get(f"https://barbars.ru/guild/{GUILD}", timeout=30)
    html = page.text
    idx = html.lower().find(NICK.lower())
    if idx < 0:
        print("герой не найден на странице клана")
        return 1
    start = html.rfind("<div>", 0, idx)
    end = html.find("<div>", idx)
    block = html[start:end if end > 0 else idx + 1500]
    text = " ".join(text_of(block).split())
    print("блок участника:", text[:200])
    m = re.search(r"(рядовой|офицер|генерал|маршал|лидер)", text)
    print("РАНГ:", m.group(1) if m else "не найден")
    print("в клане:", "да")
    return 0


if __name__ == "__main__":
    sys.exit(main())
