"""Анализ: что осталось купить firewhite (надетое, лоты магазина, кошелёк)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402
from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
SETS = ["", "/0/goliaf", "/0/atlant", "/0/veteran"]


def creds(name: str) -> tuple[str, str]:
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    return lines[0], lines[1]


def main() -> int:
    n, p = creds("barbars-firewhite-credentials.txt")
    s = login(n, p)

    body = s.get(f"{BASE}/user/body", timeout=30).text
    worn = pages.parse_worn_gear(body)
    print("=== НАДЕТОЕ (firewhite) ===")
    for w in worn:
        print(f"  {w['slot']:12} {w['name']}")

    txt = " ".join(text_of(s.get(f"{BASE}/user", timeout=30).text).split())
    m = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", txt)
    print("\nкошелёк (hp energy золото серебро железо мифрил):", m.groups() if m else "?")

    all_items = []
    for path in SETS:
        html = s.get(f"{BASE}/trade/auction/shop{path}", timeout=30).text
        items = pages.parse_shop_gear(html)
        all_items += items
    print(f"\n=== ЛОТЫ МАГАЗИНА ({len(all_items)}) ===")
    worn_slots = {w["slot"] for w in worn}
    for it in sorted(all_items, key=lambda x: (x["level"], -x["bonus"])):
        slot, _kind = pages.slot_of(it["name"])
        flag = "  <-- лучше надетого" if it["bonus"] > 0 else ""
        print(f"  {it['name']:26} {it['level']:2} ур {it['tier']:12} +{it['bonus']:4} "
              f"зол={it['gold']} сер={it['silver']} слот={slot:12}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
