"""Проверяем, что отдаёт страница таланта по разным id."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    stances = s.get("https://barbars.ru/user/stances", timeout=30)
    hrefs = sorted(set(re.findall(r'href="([^"]*talent[^"]*)"', stances.text)))
    print("найдено ссылок:", len(hrefs))
    for href in hrefs[:3] + hrefs[-1:]:
        url = "https://barbars.ru/" + href.replace("../", "").lstrip("/")
        r = s.get(url, timeout=30)
        text = " ".join(text_of(r.text).split())
        print("=" * 50)
        print(f"{href} -> {r.url}")
        print(text[:300])
        print("  есть 'выучить':", "выучить" in text.lower(), "| 'очко':", "очко" in text.lower())
        links = [h for h in sorted(set(re.findall(r'href="([^"]*)"', r.text))) if "talent" in h.lower()]
        print("  ссылки talent:", links[:6])
    return 0


if __name__ == "__main__":
    sys.exit(main())
