"""Кузнец, мастер, снаряжение: где и как железо тратится на улучшение."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def dump(s, url, label, limit=1500):
    r = s.get(url, timeout=30)
    html = r.text
    txt = " ".join(text_of(html).split())
    print(f"\n=== {label} ({url}) ===")
    print(" ", txt[:limit])
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        h = m.group(1).split("wicket:interface")[-1][:70]
        if re.search(r"(точ|улучш|закал|усил|желез|почин|кузн|мастер)", t + h, re.I):
            print(f"   {t!r} -> {h}")


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    dump(s, "https://barbars.ru/trade/smith", "кузнец")
    dump(s, "https://barbars.ru/user/master", "мастер")
    dump(s, "https://barbars.ru/user/body/id/905853", "снаряжение keis", 900)
    return 0


if __name__ == "__main__":
    sys.exit(main())
