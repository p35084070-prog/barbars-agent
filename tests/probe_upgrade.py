"""Разведка: структура /user/master (кнопки прокачки) и ссылки разбора в рюкзаке.

Только чтение страниц — ничего не ломаем и не тратим.
"""
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

        html = s.get("https://barbars.ru/user/master", timeout=30).text
        for m in re.finditer(r"moreParamsPanel:(\w+):upBlock:upLink", html):
            seg = " ".join(html[max(0, m.start() - 400):m.end() + 400].split())
            print(f"  --- {m.group(1)} ---")
            print("   ", seg[:700])
        print("  upgradeLink:", "upgradeLink" in html)
        i = html.find("upgradeLink")
        if i > 0:
            print("   mastery html:", " ".join(html[max(0, i - 400):i + 400].split())[:800])
        print("  иконки:", sorted(set(re.findall(r"icons/(money_\w+|ironbar|mifrilbar|silverbar)\.png", html))))

        rack = s.get("https://barbars.ru/user/rack", timeout=30).text
        txt = " ".join(text_of(rack).split())
        m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", txt)
        print("  рюкзак:", m.group(0) if m else "?")
        i = rack.find("crackIronPanel:crackLink")
        if i > 0:
            print("   crack html:", " ".join(rack[max(0, i - 500):i + 400].split())[:800])
        # сколько вещей с «Лучше»
        print("  'Лучше' в рюкзаке:", rack.count("Лучше"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
