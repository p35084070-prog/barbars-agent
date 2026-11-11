"""Свежий разбор страницы талантов (после 10 уровня интерфейс мог измениться)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "knowledge" / "discovered" / "fw-pages"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    stances = s.get("https://barbars.ru/user/stances", timeout=30)
    (OUT / "stances2.html").write_text(stances.text, encoding="utf-8")
    text = " ".join(text_of(stances.text).split())
    print("URL стойки:", stances.url)
    print("текст:", text[:700])
    print("--- все ссылки (уникальные, первые 30) ---")
    for h in sorted(set(re.findall(r'href="([^"]*)"', stances.text)))[:30]:
        print("  ", h)
    print("--- фрагмент HTML вокруг первого talent ---")
    m = re.search(r'href="[^"]*talent[^"]*"', stances.text)
    if m:
        print(stances.text[max(0, m.start() - 800):m.start() + 400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
