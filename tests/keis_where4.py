"""keis: мудрец (опыт за железо) и панель готовности босса."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    r = s.get("https://barbars.ru/trade/ironmaster", timeout=30)
    txt = " ".join(text_of(r.text).split())
    print("=== мудрец ===")
    print("  заголовок:", txt[:600])
    print("  iron-ссылки:", sorted(set(re.findall(r"exp\w*Link|\w+Iron\w*", r.text)))[:12])

    print("\n=== босс: панель готовности ===")
    d = s.get("https://barbars.ru/game/dragonDungeon", timeout=30)
    print("  readyLink:", len(re.findall(r"readyLink", d.text)),
          "| startCombatLink:", len(re.findall(r"startCombatLink", d.text)))
    for m in re.finditer(r"[^<>]{0,60}(Начать бой может[^<>]{0,60})", d.text):
        print("   правило:", " ".join(m.group(1).split()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
