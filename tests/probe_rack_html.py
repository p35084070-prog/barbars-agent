"""Сырой дамп рюкзака: сколько вещей, какие ссылки (разбор/надеть/в сундук)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        rack = s.get(f"{BASE}/user/rack", timeout=30).text
        txt = " ".join(text_of(rack).split())
        m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", txt)
        print(f"\n=== {label} === {m.group(0) if m else '?'}  html={len(rack)}")
        for key in ("items:", "crackLink", "crackIronPanel", "wearLink", "toStoreLink", "Лучше",
                    "personalItem", "личный"):
            print(f"   {key}: {len(re.findall(key, rack))}")
        hrefs = re.findall(r'href="([^"]*items:\d+:[^"]*)"', rack)
        print("   уникальные ссылки items (первые 12):")
        for h in list(dict.fromkeys(hrefs))[:12]:
            print("     ", h.replace("&amp;", "&"))
        # фрагмент вокруг первого items
        i = rack.find("items:")
        if i > 0:
            print("   HTML:", " ".join(rack[max(0, i - 600):i + 900].split())[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
