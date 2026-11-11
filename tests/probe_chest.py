"""Сундук firewhite: что лежит, какие тиры/«Лучше», и есть ли разбор со страницы вещи."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
TIERS = {
    "bonuscopper": "обычная",
    "bonusgreen": "необычная",
    "bonusrare": "редкая",
    "bonusepic": "эпическая",
    "bonuslegendary": "легендарная",
    "bonusdarkiron": "мифическая",
}


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    store = s.get(f"{BASE}/user/store", timeout=30).text
    txt = " ".join(text_of(store).split())
    m = re.search(r"Открыть сундук\s*\((\d+)\s*/\s*(\d+)\)", txt)
    print("сундук:", m.group(0) if m else "?")
    print("ссылки сундука:", list(dict.fromkeys(re.findall(r'href="([^"]*items:\d+:[^"]*)"', store)))[:10])

    items = []
    for chunk in store.split('<div class="hr"></div>'):
        mid = re.search(r'href="\.\./item/id/(\d+)"', chunk)
        if not mid:
            continue
        name = re.search(r"href=\"\.\./item/id/\d+\"><span>([^<]+)</span>", chunk)
        tier = "?"
        for key, label in TIERS.items():
            if key in chunk:
                tier = label
                break
        better = "Лучше" in chunk
        lvl = re.search(r"(\d+)\s*ур", " ".join(text_of(chunk).split()))
        items.append((mid.group(1), name.group(1) if name else "?", tier, better, lvl.group(1) if lvl else "?"))
    print(f"\nвещей в сундуке: {len(items)}")
    for it in items:
        print(f"  [{it[2]:11}] {'ЛУЧШЕ' if it[3] else '      '} {it[1][:34]:34} {it[4]} ур (id {it[0]})")

    # пробуем разбор со страницы вещи из сундука (самую простую вещь)
    cand = next((i for i in items if i[2] in ("обычная", "необычная", "редкая", "эпическая", "легендарная") and not i[3]), None)
    if not cand:
        print("\nнет подходящей вещи для пробы разбора")
        return 0
    item_id, name, tier, better, lvl = cand
    print(f"\nпроба разбора: {name} ({tier}, {lvl} ур, id {item_id})")
    page = s.get(f"{BASE}/item/id/{item_id}", timeout=30).text
    ptxt = " ".join(text_of(page).split())
    print("страница вещи:", ptxt[:320])
    print("  есть crack:", "crackIronPanel:crackLink" in page, "| toPublicStore:", "toPublicStoreLink" in page)
    m = re.search(r'href="([^"]*crackIronPanel:crackLink[^"]*)"', page)
    if not m:
        print("  ссылки разбора на странице вещи нет")
        return 0
    url = urljoin(f"{BASE}/item/id/{item_id}", m.group(1).replace("&amp;", "&"))
    res = s.get(url, timeout=30, headers={"Referer": f"{BASE}/item/id/{item_id}"})
    print("  HTTP", res.status_code, "->", " ".join(text_of(res.text).split())[:200])
    store2 = s.get(f"{BASE}/user/store", timeout=30).text
    print("  осталась в сундуке:", item_id in store2)
    print("  осталась в рюкзаке:", item_id in s.get(f"{BASE}/user/rack", timeout=30).text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
