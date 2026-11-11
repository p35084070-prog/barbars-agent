"""Страница одного таланта: как там выучить умение."""
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
    (OUT / "stances.html").write_text(stances.text, encoding="utf-8")
    hrefs = re.findall(r'href="([^"]*talent[^"]*)"', stances.text)
    print("ссылки на таланты:", sorted(set(hrefs))[:4])
    if not hrefs:
        return 1
    url = "https://barbars.ru/" + hrefs[0].replace("../", "").lstrip("/")
    r = s.get(url, timeout=30)
    (OUT / "talent-page.html").write_text(r.text, encoding="utf-8")
    print("URL:", r.url)
    print("\n".join(text_of(r.text).split("\n")[:40]))
    print("--- ссылки ---")
    for h in sorted(set(re.findall(r'href="([^"]*)"', r.text)))[:20]:
        print("  ", h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
