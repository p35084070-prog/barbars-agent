"""Чужая вещь на витрине: есть ли цена и кнопка покупки."""
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
    v = s.get(f"{BASE}/guild/public/store", timeout=30).text
    # парсим блоки витрины: вещь + владелец
    blocks = v.split('<div class="hr"></div>')
    for chunk in blocks:
        mid = re.search(r"item/id/(\d+)", chunk)
        if not mid:
            continue
        owner = re.search(r"user/id/(\d+)", chunk)
        name = re.search(r"<span>([^<]{3,40})</span>", chunk)
        item_id = mid.group(1)
        page = s.get(f"{BASE}/item/id/{item_id}", timeout=30).text
        t = " ".join(text_of(page).split())
        links = [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', page)) if not l.endswith(".css") and "forum" not in l and "help" not in l and "igrotop" not in l]
        print(f"\n=== {name.group(1) if name else '?'} (id {item_id}) владелец id {owner.group(1) if owner else '?'}")
        print("   ", t[:260])
        print("   ссылки:", links[:12])
        if any(k in page.lower() for k in ("buy", "price", "цена")):
            print("   >>> ЕСТЬ покупка/цена")
    return 0


if __name__ == "__main__":
    sys.exit(main())
