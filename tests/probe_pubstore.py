"""Витрина игрока: /user/public/store — что там, цены, как купить."""
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

    for path in ("/user/public/store", "/guild/public/store"):
        h = s.get(BASE + path, timeout=30)
        t = " ".join(text_of(h.text).split())
        print(f"\n======== {path} -> {h.url}")
        print(t[:1500])
        print("  ссылки:", [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', h.text))
                            if not l.endswith(".css") and "filter" not in l][:20])
        print("  buy/цена:", re.findall(r"[^.]{0,50}(?:купить|цена|золот)[^.]{0,60}", t, re.I)[:8])
    return 0


if __name__ == "__main__":
    sys.exit(main())
