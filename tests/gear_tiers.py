"""Авторазбор (активный режим), тир вещей в рюкзаке, цена улучшения у Колдуна."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

TIERS = {
    "bonuscopper": "обычная",
    "bonusgreen": "необычная",
    "bonusrare": "редкая",
    "bonusepic": "эпическая",
    "bonusdarkiron": "легендарная",
}


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])

        ac = s.get("https://barbars.ru/user/rack/autocrack", timeout=30).text
        links = set(re.findall(r"autoCrack(\w+)Link", ac))
        active = [k for k in ("Off", "Common", "Uncommon", "Rare", "Epic", "Legendary") if f"autoCrack{k}Link" not in links]
        print(f"\n=== {label} ===")
        print("  активный режим авторазбора:", active or "не найден")

        rack = s.get("https://barbars.ru/user/rack", timeout=30).text
        txt = " ".join(text_of(rack).split())
        m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", txt)
        print("  рюкзак:", m.group(0) if m else "?")
        tiers = {}
        for chunk in rack.split('<div class="hr"></div>'):
            t = " ".join(text_of(chunk).split())
            if not t or "crackLink" not in chunk and "wearLink" not in chunk:
                continue
            tier = "?"
            for key, name in TIERS.items():
                if key in chunk:
                    tier = name
                    break
            item = t.split("[")[0][:52]
            better = "Лучше" in chunk
            tiers.setdefault((tier, better), []).append(item)
        for (tier, better), items in sorted(tiers.items()):
            print(f"    тир={tier:11} лучше={better!s:5} n={len(items):2}  пример: {items[0]}")

        # Колдун: улучшение параметров вещи
        so = s.get("https://barbars.ru/trade/sorcerer", timeout=30)
        mm = re.search(r'href="([^"]*myItemsBlock:items:0:selectLink[^"]*)"', so.text)
        if not mm:
            print("  колдун: нет вещей")
            continue
        url = urljoin("https://barbars.ru/trade/sorcerer", mm.group(1).replace("&amp;", "&"))
        page = s.get(url, timeout=30)
        ptxt = " ".join(text_of(page.text).split())
        print("  колдун:", ptxt[:500])
        print("  иконки:", sorted(set(re.findall(r"icons/(money_\w+|ironbar|mifrilbar|silverbar)\.png", page.text))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
