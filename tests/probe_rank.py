"""Ранг в клане: как он растёт и кто где стоит (для доступа к боссам)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
GID = "16675"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    for path in (f"/guild/{GID}", f"/guild/participants/{GID}", f"/guild/members/{GID}"):
        h = s.get(BASE + path, timeout=30).text
        t = " ".join(text_of(h).split())
        if "Вход для игроков" in t:
            print(path, "— не открылось")
            continue
        print(f"\n=== {path} ===")
        rows = re.findall(r"([^|]{0,40}(?:нововичок|ветеран|офицер|генерал|маршал|командир)[^|]{0,60})", t)
        print("  ранги:", list(dict.fromkeys(rows))[:20])
        for key in ("Стаж", "ранг", "Ранг", "повыс", "уровень клана", "опыт клана", "Уровень"):
            for m in list(re.finditer(rf"[^.]{{0,70}}{key}[^.]{{0,110}}", t))[:3]:
                print(f"  [{key}]:", m.group(0).strip()[:180])
        print("  ссылки:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:rank|stat|level|quest|war)[^"]*)"', h)))[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
