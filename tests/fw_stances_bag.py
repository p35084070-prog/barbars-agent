"""Разбор страницы талантов и рюкзака второго героя."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "knowledge" / "discovered" / "fw-pages"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    stances = s.get("https://barbars.ru/user/stances", timeout=30)
    (OUT / "stances.html").write_text(stances.text, encoding="utf-8")
    print("=== ТАЛАНТЫ (текст) ===")
    print("\n".join(text_of(stances.text).split("\n")[:60]))
    print("=== ТАЛАНТЫ (ссылки) ===")
    for href in sorted(set(re.findall(r'href="([^"]*)"', stances.text))):
        if "talent" in href.lower() or "stance" in href.lower():
            print("  ", href)

    bag = s.get("https://barbars.ru/user/rack", timeout=30)
    (OUT / "bag2.html").write_text(bag.text, encoding="utf-8")
    print("=== РЮКЗАК (текст) ===")
    print("\n".join(text_of(bag.text).split("\n")[:45]))
    print("=== РЮКЗАК (ссылки на предметы) ===")
    for href in sorted(set(re.findall(r'href="([^"]*)"', bag.text))):
        if any(k in href.lower() for k in ("item", "rack", "chest", "box", "sale", "sell")):
            print("  ", href)
    return 0


if __name__ == "__main__":
    sys.exit(main())
