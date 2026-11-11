"""Колдун: цена улучшения параметров вещи. Мастерство firewhite."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    html = s.get("https://barbars.ru/trade/masters", timeout=30).text
    print("=== ссылки мастеров ===")
    for m in re.finditer(r"<a[^>]+href=\"([^\"]*trade/[^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        if t:
            print(f"   {t!r} -> {m.group(1)}")

    # Колдун: первая вещь и её улучшение
    k = s.get("https://barbars.ru/trade/alchemist", timeout=30)
    khtml = k.text
    m = re.search(r"<a[^>]+href=\"([^\"]*selectLink[^\"]*)\"", khtml)
    print("\n=== колдун: текст ===")
    print(" ", " ".join(text_of(khtml).split())[:600])
    print("  иконки:", sorted(set(re.findall(r"money_\w+\.png|ironbar\.png|mifrilbar\.png|silverbar\.png", khtml))))
    if m:
        url = "https://barbars.ru/trade/alchemist"
        print("  selectLink:", m.group(1)[:100])

    # мастерство firewhite
    fl = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    fl = [l for l in fl if l]
    s2 = login(fl[0], fl[1])
    mm = s2.get("https://barbars.ru/user/master", timeout=30)
    print("\n=== мастерство firewhite ===")
    print(" ", " ".join(text_of(mm.text).split())[:700])
    print("  иконки:", sorted(set(re.findall(r"money_\w+\.png|ironbar\.png|mifrilbar\.png", mm.text))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
