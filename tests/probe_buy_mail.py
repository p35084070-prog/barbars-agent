"""Разведка: покупка вещи на витрине клана, почта, золото героя."""
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

    # 1. ресурсы (золото)
    res = " ".join(text_of(s.get(f"{BASE}/user/resources", timeout=30).text).split())
    print("РЕСУРСЫ:", res[:300])

    # 2. главная — где почта
    home = s.get(f"{BASE}/", timeout=30)
    ht = " ".join(text_of(home.text).split())
    print("\nГЛАВНАЯ (начало):", ht[:400])
    print("почта-ссылки:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:mail|post|letter)[^"]*)"', home.text)))[:8])
    for m in list(re.finditer(r"[^.]{0,50}(?:почт|письм|новост)[^.]{0,60}", ht, re.I))[:6]:
        print("  ПОЧТА:", m.group(0).strip()[:120])

    # 3. витрина: ссылки покупки
    v = s.get(f"{BASE}/guild/public/store", timeout=30).text
    print("\nВИТРИНА ссылки:", list(dict.fromkeys(re.findall(r'href="([^"]+)"', v)))[:26])
    vt = " ".join(text_of(v).split())
    for m in list(re.finditer(r"[^.]{0,60}(?:купить|цена|золот|серебр|купи)[^.]{0,80}", vt, re.I))[:10]:
        print("  ВИТРИНА:", m.group(0).strip()[:150])
    print("  buy-ссылки:", list(dict.fromkeys(re.findall(r'href="([^"]*(?:buy|price|buyLink|order)[^"]*)"', v)))[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
