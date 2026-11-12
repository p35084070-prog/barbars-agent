"""Что надето на герое: названия вещей по слотам (/user/body)."""
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
    hero = s.get(f"{BASE}/user", timeout=30).text
    m = re.search(r"user/body/id/(\d+)", hero)
    print("body url:", m.group(0) if m else "?")
    body = s.get(f"{BASE}/user/body/id/{m.group(1)}", timeout=30).text if m else ""
    t = " ".join(text_of(body).split())
    print("ТЕКСТ:", t[:900])
    print("\nссылки item/id:", list(dict.fromkeys(re.findall(r"item/id/(\d+)", body)))[:12])
    print("названия:", re.findall(r"<span>([А-ЯЁ][^<]{2,40})</span>", body)[:25])
    return 0


if __name__ == "__main__":
    sys.exit(main())
