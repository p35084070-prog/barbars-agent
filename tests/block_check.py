"""Точный формат ссылки crackLink и блок предмета."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    h = s.get("https://barbars.ru/user/rack", timeout=30).text

    pats = sorted(set(re.findall(r'href="[^"]*crackLink[^"]*"', h)))
    print("=== уникальные ссылки crackLink ===")
    for p in pats[:8]:
        print("  ", p)
    print("  всего уникальных:", len(pats))

    print("\n=== блоки: индекс + действия ===")
    for chunk in h.split('<div class="hr"></div>'):
        idx = re.findall(r"items:(\d+):(\w+)", chunk)
        if not idx:
            continue
        acts = sorted({a for _, a in idx})
        better = "Лучше" in chunk
        name = " ".join(re.sub(r"<[^>]+>", " ", chunk).split())[:60]
        print(f"   idx={idx[0][0]:>3} acts={acts} лучше={better} | {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
