"""Магазин снаряжения: товары, цены, ссылки покупки (25 ур. вещи)."""
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
    for path in ("/trade/auction/shop", "/trade/legioner", "/trade/hunter/shop"):
        h = s.get(BASE + path, timeout=30)
        t = " ".join(text_of(h.text).split())
        print(f"\n======== {path} -> {h.url}")
        print(t[:1200])
        links = [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', h.text)) if not l.endswith(".css")]
        print("  ссылки:", links[:20])
        print("  'купить' в тексте:", "Купить" in t or "купить" in t)
        for m in list(re.finditer(r"[^.]{0,60}(?:Купить|Цена|цена)[^.]{0,80}", t))[:8]:
            print("   ", m.group(0).strip()[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
