"""Клановые события: боссы, требования, участники, награды + наши статы."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"

PAGES = [
    ("Мифический дракон", "/game/dragonDungeon"),
    ("Святилище предков", "/game/greatBoss"),
    ("Битва героев", "/game/battle"),
    ("Замок 6", "/castle/6"),
    ("Замок 8", "/castle/8"),
    ("Арена", "/game/arena"),
    ("Выживание", "/game/survival"),
]


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n================ {label} ================")

        # наши параметры
        m = s.get(f"{BASE}/user/master", timeout=30).text
        mt = " ".join(text_of(m).split())
        i = mt.find("Улучшение параметров")
        print("  ПАРАМЕТРЫ:", mt[i:i + 700] if i >= 0 else mt[:400])

        for name, path in PAGES:
            try:
                h = s.get(BASE + path, timeout=30).text
            except Exception as exc:
                print(f"  --- {name}: ошибка {exc}")
                continue
            t = " ".join(text_of(h).split())
            head = t[:260]
            req = [m.group(0).strip() for m in re.finditer(r"[^.]{0,70}(?:нужно|требу|необходим|сила|жизн|уровень|участник|вступить|присоедин)[^.]{0,90}", t)][:6]
            btns = [b for b in dict.fromkeys(re.findall(r">([^<>]{3,40})</(?:a|button)>", h)) if any(
                k in b.lower() for k in ("бой", "готов", "начать", "вступи", "участ", "ата"))][:6]
            print(f"  --- {name} ({path})")
            print("     ", head[:230])
            if req:
                print("      требования:", " | ".join(req)[:300])
            if btns:
                print("      кнопки:", btns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
