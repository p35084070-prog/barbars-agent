"""Проверка парсера магазина снаряжения по всем наборам."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402
from game_state import DESKTOP, login  # noqa: E402

BASE = "https://barbars.ru"
SETS = ["", "/0/goliaf", "/0/atlant", "/0/veteran"]


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    all_items = []
    for path in SETS:
        url = f"{BASE}/trade/auction/shop{path}"
        html = s.get(url, timeout=30).text
        items = pages.parse_shop_gear(html)
        all_items += items
        print(f"\n=== {path or 'берсерк'} — {len(items)} товаров")
        for it in items:
            print(f"   {it['name']:26} {it['level']:2} ур {it['tier']:12} +{it['bonus']:4} "
                  f"золото={it['gold']} серебро={it['silver']} id={it['item_id']}")
    cheap = [i for i in all_items if i["gold"] <= 3 and i["gold"] > 0]
    print(f"\nдешевле 3 золота: {len(cheap)}")
    for it in sorted(cheap, key=lambda x: (-x["bonus"])):
        print(f"   {it['name']:26} +{it['bonus']:4} золото={it['gold']} серебро={it['silver']} {it['tier']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
