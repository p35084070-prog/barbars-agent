"""Аукцион: какие типы товаров можно выставлять (есть ли вещи) и вкладки фильтров."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    h = s.get(f"{BASE}/trade/bazaar", timeout=30).text
    print("ФИЛЬТРЫ:", list(dict.fromkeys(re.findall(r'href="([^"]*filter\w*Link[^"]*)"', h))))
    print("ТИПЫ ТОВАРОВ (select):")
    for sel in re.findall(r"<select[^>]*name=[\"']type[\"'][^>]*>(.*?)</select>", h, re.S):
        for opt in re.findall(r"<option[^>]*value=[\"'](\d+)[\"'][^>]*>(.*?)</option>", sel, re.S):
            print("   ", opt[0], "-", " ".join(text_of(opt[1]).split()))
    print("кнопки:", list(dict.fromkeys(re.findall(r'>([^<>]{2,40})</a>', h)))[:25])
    # общее хранилище клана
    for url in (f"{BASE}/guild/public/store",):
        try:
            p = s.get(url, timeout=30).text
            t = " ".join(text_of(p).split())
            print("\nОБЩЕЕ ХРАНИЛИЩЕ:", t[:500])
            print("  ссылки:", list(dict.fromkeys(re.findall(r'href="([^"]*items:\d+:[^"]*)"', p)))[:8])
        except Exception as exc:
            print(url, "ошибка", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
