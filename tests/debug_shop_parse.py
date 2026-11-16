"""Отладка парсера лотов магазина на свежем HTML."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402
from game_state import DESKTOP, login  # noqa: E402

BASE = "https://barbars.ru"


def creds(name: str) -> tuple[str, str]:
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    return lines[0], lines[1]


def main() -> int:
    n, p = creds("barbars-firewhite-credentials.txt")
    s = login(n, p)
    html = s.get(f"{BASE}/trade/auction/shop", timeout=30).text
    print("len", len(html))
    print("chunks", len(html.split('<div class="hr"></div>')))
    print("regexA", len(re.findall(r'href="[^"]*shop/item/id/(\d+)"><span>([^<]+)</span>', html)))
    print("regexB", len(re.findall(r'href="(?:\.\./)*(trade/auction/shop/item/id/(\d+))"><span>([^<]+)</span>', html)))
    items = pages.parse_shop_gear(html)
    print("parsed", len(items))
    for it in items:
        print(f"  {it['name']:26} {it['level']:2} ур +{it['bonus']:4} зол={it['gold']} сер={it['silver']} ok={it['price_ok']}")
    # сырой фрагмент одного лота
    i = html.find("shop/item/id/")
    print("\nФРАГМЕНТ:\n", " ".join(html[max(0, i - 900):i + 900].split())[:2200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
