"""Живая проверка разбора вещей на железо (любой аккаунт).

Показывает содержимое рюкзака и ломает ОДНУ вещь (самую обычную, без «Лучше»),
чтобы проверить, что ссылка crackIronPanel:crackLink работает.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def rack_items(s) -> list[tuple[str, str, bool]]:
    html = s.get(f"{BASE}/user/rack", timeout=30).text
    out = []
    for chunk in html.split('<div class="hr"></div>'):
        m = re.search(r'href="([^"]*items:(\d+):[^"]*crackIronPanel:crackLink[^"]*)"', chunk)
        if not m:
            continue
        name = re.search(r"<span>([^<]{2,60})</span>\s*</a>", chunk)
        tier = "?"
        for key, label in (("bonuscopper", "обычная"), ("bonusgreen", "необычная"),
                           ("bonusrare", "редкая"), ("bonusepic", "эпическая"),
                           ("bonusdarkiron", "легендарная")):
            if key in chunk:
                tier = label
                break
        iron = re.search(r"icons/ironbar\.png[^>]*/>\s*<span>([\d.,]+[KkMm]?)</span>", chunk)
        out.append((name.group(1) if name else "?", tier, "Лучше" in chunk,
                    m.group(1), iron.group(1) if iron else "?"))
    return out


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        items = rack_items(s)
        print(f"\n=== {label}: рюкзак, вещей с разбором: {len(items)} ===")
        for name, tier, better, href, iron in items:
            print(f"  [{tier:10}] {'ЛУЧШЕ' if better else '      '} {name:32} железо {iron}")
        if not items:
            print("  (разбирать нечего)")
            continue
        # ломаем первую обычную вещь без «Лучше»
        target = next((i for i in items if not i[2]), items[0])
        url = urljoin(f"{BASE}/user/rack", target[3].replace("&amp;", "&"))
        res = s.get(url, timeout=30, headers={"Referer": f"{BASE}/user/rack"})
        after = rack_items(s)
        print(f"  >> разорвали «{target[0]}» ({target[1]}), осталось вещей: {len(after)} "
              f"(было {len(items)}), HTTP {res.status_code}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
