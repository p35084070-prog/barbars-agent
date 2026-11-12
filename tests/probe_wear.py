"""Проба надевания «Лучше»: клик wearLink и что происходит."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    rack = s.get(f"{BASE}/user/rack", timeout=30).text
    # первый блок с «Лучше» и ссылкой «надеть»
    target = None
    for chunk in rack.split('<div class="hr"></div>'):
        if "Лучше" not in chunk:
            continue
        m = re.search(r'href="([^"]*items:(\d+):wearLink[^"]*)"', chunk)
        name = re.search(r"item/id/\d+\"><span>([^<]+)</span>", chunk)
        if m:
            target = (m.group(1), m.group(2), name.group(1) if name else "?")
            break
    if not target:
        print("нет вещи «Лучше» с wearLink")
        return 1
    href, index, name = target
    print("цель:", name, "index", index)
    url = urljoin(f"{BASE}/user/rack", href.replace("&amp;", "&"))
    print("URL:", url)
    res = s.get(url, timeout=30, headers={"Referer": f"{BASE}/user/rack"})
    t = " ".join(text_of(res.text).split())
    print("ОТВЕТ:", t[:700])
    print("\nесть confirm/подтверждение:", bool(re.search(r"confirm|подтверд|Заменить|заменить", res.text, re.I)))
    body = s.get(f"{BASE}/user/body/id/31389504", timeout=30).text
    bt = " ".join(text_of(body).split())
    i = bt.find("Моё снаряжение")
    print("\nСНАРЯЖЕНИЕ:", bt[i:i + 500])
    rack2 = s.get(f"{BASE}/user/rack", timeout=30).text
    print("\nосталось в рюкзаке:", " ".join(text_of(rack2).split())[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
