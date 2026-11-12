"""Сырой HTML блока витрины: ищем кнопку покупки/цену (то, что не видно в тексте)."""
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
    i = v.find("Кираса Атланта")
    print("HTML вокруг Кирасы Атланта:\n")
    print(" ".join(v[max(0, i - 1500):i + 1500].split())[:3000])
    print("\n\nвсе уникальные wicket-ссылки витрины:")
    for l in dict.fromkeys(re.findall(r'href="([^"]*wicket[^"]*)"', v)):
        print("  ", l)
    print("\ninput/select на витрине:", re.findall(r"<input[^>]*>", v)[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
