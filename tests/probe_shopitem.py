"""Страница товара в магазине снаряжения (кнопка покупки) + почта (забрать)."""
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

    # список товаров магазина: цена в HTML (иконки золота/серебра)
    shop = s.get(f"{BASE}/trade/auction/shop", timeout=30).text
    print("=== МАГАЗИН (фрагменты цен) ===")
    for m in list(re.finditer(r"цена[^<]{0,40}", shop))[:6]:
        print("  ", " ".join(m.group(0).split())[:80])
    for m in list(re.finditer(r"цена.{0,400}", shop, re.S))[:3]:
        print("  HTML цены:", " ".join(m.group(0).split())[:300])

    # страница товара
    item = s.get(f"{BASE}/trade/auction/shop/item/id/40098977", timeout=30)
    t = " ".join(text_of(item.text).split())
    print("\n=== СТРАНИЦА ТОВАРА ===")
    print(t[:600])
    links = [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', item.text)) if not l.endswith(".css")]
    print("  ссылки:", links[:14])
    print("  buy:", [l for l in links if "buy" in l.lower()])

    # почта: ссылка «забрать всё»
    mail = s.get(f"{BASE}/user/mail", timeout=30)
    mt = " ".join(text_of(mail.text).split())
    print("\n=== ПОЧТА ===")
    print(mt[:500])
    mlinks = [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', mail.text)) if not l.endswith(".css")]
    print("  ссылки:", mlinks[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main())
