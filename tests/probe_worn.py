"""Проверка парсера надетого снаряжения."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402
from game_state import DESKTOP, login  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    hero = s.get(f"{BASE}/user", timeout=30).text
    import re
    hid = re.search(r"user/body/id/(\d+)", hero).group(1)
    body = s.get(f"{BASE}/user/body/id/{hid}", timeout=30).text
    worn = pages.parse_worn_gear(body)
    print("надето:", worn)
    for w in worn:
        print("   ", w["slot"], "|", w["name"], "->", pages.slot_of(w["name"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
