"""Проверка витрины клана и рюкзака после выставления вещи (firewhite)."""
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
    v = s.get(f"{BASE}/guild/public/store", timeout=30).text
    t = " ".join(text_of(v).split())
    print("ВИТРИНА:", t[:1200])
    print()
    print("item ids:", list(dict.fromkeys(re.findall(r"item/id/(\d+)", v)))[:12])
    rack = s.get(f"{BASE}/user/rack", timeout=30).text
    print("РЮКЗАК:", " ".join(text_of(rack).split())[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
