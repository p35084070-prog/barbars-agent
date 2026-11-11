"""Клановый стаж и опыт: что нужно, чтобы открылись клановые боссы."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
GID = "16675"


def main() -> int:
    for label, fname in (("firewhite", "barbars-firewhite-credentials.txt"),
                         ("keis", "barbars-agentcredentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n======== {label} ========")
        for path in (f"/guild/stat/0/{GID}", f"/guild/stat/time/0/{GID}"):
            h = s.get(BASE + path, timeout=30).text
            t = " ".join(text_of(h).split())
            print(f"  --- {path}")
            i = t.find("Стаж")
            print("   ", t[max(0, i - 150):i + 500] if i >= 0 else t[:450])
        # участники и их стаж
        h = s.get(f"{BASE}/guild/participants/{GID}", timeout=30).text
        t = " ".join(text_of(h).split())
        print("  --- участники:", t[t.find("Рейтинг клана") - 700:t.find("Рейтинг клана")][:700])
    return 0


if __name__ == "__main__":
    sys.exit(main())
