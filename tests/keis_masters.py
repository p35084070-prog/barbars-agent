"""Лавка мастеров (прокачка железом), сундук (разбор), авторазбор — по страницам."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def dump(s, url, label, limit=1200):
    r = s.get(url, timeout=30)
    html = r.text
    txt = " ".join(text_of(html).split())
    print(f"\n=== {label} ===")
    print(" ", txt[:limit])
    links = set()
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        h = m.group(1).split("wicket:interface")[-1][:60]
        if t in ("Выход", "Обновить", "Вернуться в бой", "Мой герой", "Мой клан", "На главную"):
            continue
        links.add((t[:45], h))
    for t, h in list(links)[:25]:
        print(f"   {t!r} -> {h}")
    return html


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    dump(s, "https://barbars.ru/trade/masters", "лавка мастеров")
    dump(s, "https://barbars.ru/user/store", "сундук keis", 800)
    dump(s, "https://barbars.ru/user/rack/autocrack", "авторазбор", 700)
    return 0


if __name__ == "__main__":
    sys.exit(main())
