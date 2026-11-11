"""Лавка мастеров целиком + страница акций (скидка на Заточника)."""
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

    for url, label in (("https://barbars.ru/trade/masters", "мастера"),
                       ("https://barbars.ru/action", "акции")):
        html = s.get(url, timeout=30).text
        txt = " ".join(text_of(html).split())
        print(f"\n=== {label} ===")
        print(" ", txt[:1200])
        for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
            t = " ".join(text_of(m.group(2)).split())
            h = m.group(1)
            if re.search(r"(заточ|точил|точиль|grind|smith|goldsmith|ювелир|кузнец|заточник)", t + h, re.I):
                print(f"   {t!r} -> {h.split('wicket:interface')[-1][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
