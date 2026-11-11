"""Разметка кнопок: арена, выживание, готовность босса."""
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

    for label, url, needle in (
        ("арена", "https://barbars.ru/game/arena", "Встать в очередь"),
        ("выживание", "https://barbars.ru/game/survival", "Встать в очередь"),
        ("дракон", "https://barbars.ru/game/dragonDungeon", "Я готов"),
    ):
        html = s.get(url, timeout=30).text
        i = html.find(needle)
        print(f"\n=== {label} ({needle}) ===")
        if i < 0:
            print("  не найдено")
            continue
        print(" ", " ".join(html[max(0, i - 300):i + 200].split()))

    print("\n=== замки ===")
    for cid in (6, 8):
        html = s.get(f"https://barbars.ru/castle/{cid}", timeout=30).text
        txt = " ".join(text_of(html).split())
        print(f"  castle/{cid}:", txt[:260])
        for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
            t = " ".join(text_of(m.group(2)).split())
            if re.search(r"(Войти|Замок|замок|Атака)", t + m.group(1)):
                print(f"    {t!r} -> {m.group(1)[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
