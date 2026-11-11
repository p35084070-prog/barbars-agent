"""Ссылки мастеров из Лавки + стоимость улучшения параметров вещи."""
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
    urls = {}
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        if t and t not in ("Выход", "Обновить", "Мой герой", "Мой клан", "На главную"):
            urls[t] = m.group(1)
    print("мастера:", urls)

    for name, href in urls.items():
        if name in ("Мудрец",):
            continue
        url = "https://barbars.ru/" + href.lstrip("./").replace("../", "")
        page = s.get(url, timeout=30)
        txt = " ".join(text_of(page.text).split())
        icons = sorted(set(re.findall(r"money_\w+\.png|ironbar\.png|mifrilbar\.png|silverbar\.png", page.text)))
        print(f"\n=== {name} ({url}) ===")
        print("  ", txt[:700])
        print("  иконки:", icons)
    return 0


if __name__ == "__main__":
    sys.exit(main())
