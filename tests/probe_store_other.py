"""Можно ли забрать чужую вещь с витрины игрока (/user/public/store/<id>)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
KEIS = "905853"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    for url in (f"{BASE}/user/public/store/{KEIS}", f"{BASE}/user/public/store", f"{BASE}/user/id/{KEIS}"):
        h = s.get(url, timeout=30)
        t = " ".join(text_of(h.text).split())
        print(f"\n=== {url} -> {h.url} (len {len(h.text)})")
        print("  ", t[:600])
        print("  toRack:", list(dict.fromkeys(re.findall(r'href="([^"]*toRackLink[^"]*)"', h.text)))[:6])
        print("  item ids:", list(dict.fromkeys(re.findall(r"item/id/(\d+)", h.text)))[:6])
    return 0


if __name__ == "__main__":
    sys.exit(main())
