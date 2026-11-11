"""Подробно: поход, клановые боссы, арена — что можно нажать."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def dump(s, url, label):
    r = s.get(url, timeout=30)
    html = r.text
    txt = " ".join(text_of(html).split())
    print(f"\n=== {label} ===")
    print(txt[:1100])
    print("--- ссылки ---")
    seen = set()
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        h = m.group(1)
        if t in ("Выход", "Обновить", "Вернуться в бой"):
            continue
        key = (t, h.split("wicket:interface")[-1][:60])
        if key in seen:
            continue
        seen.add(key)
        print(f"   {t[:45]!r} -> {key[1]}")


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    dump(s, "https://barbars.ru/journey", "поход")
    dump(s, "https://barbars.ru/game/dragonDungeon", "дракон")
    dump(s, "https://barbars.ru/game/towers", "башня keis")
    dump(s, "https://barbars.ru/game/towers/map", "карта башен")
    return 0


if __name__ == "__main__":
    sys.exit(main())
