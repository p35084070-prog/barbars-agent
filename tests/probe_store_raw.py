"""Сырой HTML витрины firewhite — ищем поля цены (золото/серебро)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login  # noqa: E402

BASE = "https://barbars.ru"


def creds(name: str) -> tuple[str, str]:
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    return lines[0], lines[1]


def main() -> int:
    n, p = creds("barbars-firewhite-credentials.txt")
    s = login(n, p)
    html = s.get(f"{BASE}/user/public/store", timeout=30).text
    print("=== RAW витрины (3500 симв.) ===")
    print(" ".join(html.split())[:3500])
    print("\n=== поиск цена/price/cost ===")
    for m in re.finditer(r"(цена|price|cost|gold|silver)", html, re.I):
        print("  ...", " ".join(html[max(0, m.start() - 120):m.start() + 160].split())[:280])
        if m.start() > 0 and len(re.findall(r"(?:цена|price|cost)", html[:m.start()], re.I)) > 8:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
