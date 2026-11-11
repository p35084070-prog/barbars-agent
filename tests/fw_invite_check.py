"""Что видит новый герой на главной: есть ли приглашение в клан."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    home = s.get("https://barbars.ru/", timeout=30)
    print("=== главная ===")
    print("\n".join(text_of(home.text).split("\n")[:40]))
    print("=== ссылки ===")
    for href in sorted(set(re.findall(r'href="([^"]+)"', home.text))):
        if "style.css" not in href:
            print("  ", href)
    guild = s.get("https://barbars.ru/guild/16675", timeout=30)
    print("=== страница клана глазами героя ===")
    print("\n".join(text_of(guild.text).split("\n")[:45]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
