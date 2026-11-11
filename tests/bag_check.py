"""firewhite: рюкзак/сундук; keis: валюта похода (по html)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def rack_of(nick, password, label):
    s = login(nick, password)
    t = " ".join(text_of(s.get("https://barbars.ru/user/rack", timeout=30).text).split())
    bag = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", t)
    chest = re.search(r"Открыть сундук\s*\((\d+)\s*/\s*(\d+)\)", t)
    print(f"{label}: рюкзак={bag.group(0) if bag else '?'} сундук={chest.group(0) if chest else '?'}")
    return s


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = rack_of(lines[0], lines[1], label)
        if label == "keis":
            j = s.get("https://barbars.ru/journey", timeout=30).text
            i = j.find("buy8Link")
            chunk = j[max(0, i - 400):i + 100]
            print("\n=== html похода (фрагмент) ===")
            print(chunk[-700:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
