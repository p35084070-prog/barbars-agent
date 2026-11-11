"""Есть ли разбор вещей в сундуке (crackAll / crackLink) и что даёт «Разобрать всё»."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n=== {label} ===")
        for page, name in (("https://barbars.ru/user/rack", "рюкзак"),
                           ("https://barbars.ru/user/store", "сундук")):
            html = s.get(page, timeout=30).text
            print(f"  {name}: crackAll={len(re.findall('crackAll', html))} "
                  f"crackLink={len(re.findall('crackLink', html))} "
                  f"wearLink={len(re.findall('wearLink', html))} "
                  f"toRack={len(re.findall('toRackLink', html))} "
                  f"sendToStorage={len(re.findall('sendToGuildStorage', html))}")
            txt = " ".join(text_of(html).split())
            m = re.search(r"Разобрать всё[^]]*", txt)
            if m:
                print("   ", m.group(0)[:120])
        # что именно даёт разбор — цена иконка
        html = s.get("https://barbars.ru/user/rack", timeout=30).text
        i = html.find("crackAllIronLink")
        if i > 0:
            print("   'Разобрать всё' html:", " ".join(html[max(0, i - 200):i + 300].split())[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
