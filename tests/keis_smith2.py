"""Страница прокачки вещи у кузнеца: цена и что нужно."""
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

    r = s.get("https://barbars.ru/trade/smith/id/1950177878", timeout=30)
    html = r.text
    txt = " ".join(text_of(html).split())
    print("=== кузнец: прокачка «Наручи Ветерана» ===")
    print(" ", txt[:1500])
    print("  иконки денег:", sorted(set(re.findall(r"money_\w+\.png|ironbar\.png|mifrilbar\.png", html))))
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        h = m.group(1).split("wicket:interface")[-1][:70]
        if re.search(r"(повыс|улучш|запчаст|купить|уровен)", t + h, re.I):
            print(f"   {t!r} -> {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
