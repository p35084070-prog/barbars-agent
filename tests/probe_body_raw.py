"""Сырой фрагмент страницы снаряжения — чтобы починить парсер надетого."""
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
    body = s.get(f"{BASE}/user/body/id/31389504", timeout=30).text
    i = body.find("Шлем")
    print("HTML вокруг «Шлем»:\n", " ".join(body[max(0, i - 600):i + 900].split())[:2200])
    print("\n--- текст:")
    t = " ".join(text_of(body).split())
    j = t.find("Моё снаряжение")
    print(t[j:j + 700])
    return 0


if __name__ == "__main__":
    sys.exit(main())
