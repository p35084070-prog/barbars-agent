"""Проверка: разбор эпической вещи через страницу вещи (keis)."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    def iron_now() -> int:
        r = s.get(f"{BASE}/user/resources", timeout=30).text
        m = re.search(r"Железо:\s*([\d,]+)", " ".join(text_of(r).split()))
        return int(m.group(1).replace(",", "")) if m else -1

    rack = s.get(f"{BASE}/user/rack", timeout=30).text
    print("железо до:", iron_now())
    target = None
    for chunk in rack.split('<div class="hr"></div>'):
        if "bonusepic" not in chunk:
            continue
        if "Лучше" in chunk:
            continue
        if "crackIronPanel:crackLink" in chunk:
            print("в списке есть crack-ссылка — не нужно через страницу")
            continue
        mid = re.search(r'href="\.\./item/id/(\d+)"', chunk)
        name = re.search(r"href=\"\.\./item/id/\d+\"><span>([^<]+)</span>", chunk)
        if mid:
            target = (mid.group(1), name.group(1) if name else "?")
            break
    if not target:
        print("подходящей вещи нет")
        return 1
    item_id, name = target
    print(f"цель: {name} (id {item_id})")
    page = s.get(f"{BASE}/item/id/{item_id}", timeout=30)
    ptxt = " ".join(text_of(page.text).split())
    print("страница вещи:", ptxt[:260])
    m = re.search(r'href="([^"]*crackIronPanel:crackLink[^"]*)"', page.text)
    if not m:
        print("ссылки разбора на странице вещи нет")
        return 1
    url = urljoin(f"{BASE}/item/id/{item_id}", m.group(1).replace("&amp;", "&"))
    print("жмём:", url)
    res = s.get(url, timeout=30, headers={"Referer": f"{BASE}/item/id/{item_id}"})
    print("HTTP", res.status_code, "->", " ".join(text_of(res.text).split())[:300])
    print("железо после:", iron_now())
    rack2 = s.get(f"{BASE}/user/rack", timeout=30).text
    print("осталось вещей с id", item_id, ":", item_id in rack2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
