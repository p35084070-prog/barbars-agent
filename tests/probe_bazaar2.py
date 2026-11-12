"""Аукцион (/trade/bazaar): вкладки, типы товаров, есть ли вещи."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    for label, fname in (("firewhite", "barbars-firewhite-credentials.txt"),
                         ("keis", "barbars-agentcredentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        h = s.get(f"{BASE}/trade/bazaar", timeout=30)
        t = " ".join(text_of(h.text).split())
        print(f"\n======== {label} ======== url={h.url} len={len(h.text)}")
        print("  текст:", t[:900])
        print("  filter-ссылки:", list(dict.fromkeys(re.findall(r'href="([^"]*filter\w*Link[^"]*)"', h.text)))[:12])
        for sel in re.findall(r"<select[^>]*>(.*?)</select>", h.text, re.S):
            opts = re.findall(r"<option[^>]*value=[\"']?(\d*)[\"']?[^>]*>(.*?)</option>", sel, re.S)
            if opts:
                print("  select:", [(o[0], " ".join(text_of(o[1]).split())) for o in opts][:12])
        print("  ссылки на аукционе:", [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', h.text))
                                       if "wicket" in l][:14])
        # аукцион предметов? ищем вкладки «Вещи»
        print("  есть 'item' в разметке:", len(re.findall(r"item/id/\d+", h.text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
