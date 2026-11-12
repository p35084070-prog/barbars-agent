"""Рюкзак firewhite: есть ли вещи «Лучше» и ссылка «надеть»."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    rack = s.get(f"{BASE}/user/rack", timeout=30).text
    t = " ".join(text_of(rack).split())
    i = t.find("Рюкзак")
    print("РЮКЗАК:", t[i:i + 700])
    print("\nwearLink:", len(re.findall("wearLink", rack)), "| 'Лучше':", rack.count("Лучше"))
    for chunk in rack.split('<div class="hr"></div>'):
        if "item/id" not in chunk:
            continue
        name = re.search(r"item/id/\d+\"><span>([^<]+)</span>", chunk)
        print("  вещь:", name.group(1) if name else "?",
              "| Лучше:", "Лучше" in chunk,
              "| надеть:", "wearLink" in chunk,
              "| разобрать:", "crackLink" in chunk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
