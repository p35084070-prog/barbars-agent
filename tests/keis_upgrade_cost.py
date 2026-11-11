"""Точные цены: мастерство (оба героя) и параметры вещи у Колдуна."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def master_blocks(html):
    """Разбор блоков параметров на /user/master: имя, ссылка, цена, валюта."""
    out = []
    for m in re.finditer(r"moreParamsPanel:(\w+):upBlock:upLink", html):
        seg = html[max(0, m.start() - 800):m.end() + 500]
        icons = re.findall(r"icons/(money_\w+|ironbar|mifrilbar|silverbar)\.png", seg)
        nums = re.findall(r"<span>(\d[\d.,]*[KkMm]?)</span>", seg)
        out.append((m.group(1), icons[-2:], nums[-2:]))
    return out


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])

        html = s.get("https://barbars.ru/user/master", timeout=30).text
        print(f"\n=== мастерство {label} ===")
        i = html.find("upgradeLink")
        print("  повышение уровня:", " ".join(html[max(0, i - 300):i + 300].split())[:400])
        for name, icons, nums in master_blocks(html):
            print(f"   {name}: иконки={icons} числа={nums}")

        k = s.get("https://barbars.ru/trade/sorcerer", timeout=30)
        khtml = k.text
        print(f"  --- колдун {label} ---")
        print("  ", " ".join(text_of(khtml).split())[:400])
        print("  иконки:", sorted(set(re.findall(r"icons/(money_\w+|ironbar|mifrilbar|silverbar)\.png", khtml))))
        mm = re.search(r"selectLink", khtml)
        if mm:
            print("  есть selectLink")
    return 0


if __name__ == "__main__":
    sys.exit(main())
