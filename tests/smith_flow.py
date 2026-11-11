"""Кузнец: полный флоу прокачки вещи (выбор запчасти -> подтверждение)."""
from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    html = s.get("https://barbars.ru/trade/smith", timeout=30).text
    print("=== кузнец: блоки вещей ===")
    for m in re.finditer(r"<a[^>]+href=\"([^\"]*trade/smith/id/\d+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        print(f"   {m.group(1)}")
    print("  «Есть N вещь на запчасти»:",
          re.findall(r"Есть (\d+) вещ\w* на запчасти", text_of(html)))

    url = "https://barbars.ru/trade/smith/id/1950177878"
    page = s.get(url, timeout=30)
    print("\n=== страница прокачки ===")
    print(" ", " ".join(text_of(page.text).split())[:700])
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", page.text, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        h = m.group(1).split("wicket:interface")[-1][:80]
        if t and t not in ("Выход", "Мой герой", "Мой клан", "На главную"):
            print(f"   {t!r} -> {h}")

    # кликаем выбор запчасти и смотрим, что дальше
    mm = re.search(r'href="([^"]*spareItemsBlock:spareItems:0:selectLink[^"]*)"', page.text)
    if mm:
        u2 = urljoin(url, mm.group(1).replace("&amp;", "&"))
        p2 = s.get(u2, timeout=30)
        print("\n=== после выбора запчасти ===")
        print(" ", " ".join(text_of(p2.text).split())[:700])
        for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", p2.text, re.S | re.I):
            t = " ".join(text_of(m.group(2)).split())
            h = m.group(1).split("wicket:interface")[-1][:80]
            if t and t not in ("Выход", "Мой герой", "Мой клан", "На главную", "Лавка мастеров"):
                print(f"   {t!r} -> {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
