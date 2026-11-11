"""Витрина клана: как выставить вещь на продажу; аукцион ресурсов (keis)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n======== {label} ========")

        # аукцион (ресурсы)
        b = s.get(f"{BASE}/trade/bazaar", timeout=30).text
        print("  БАЗАР url:", s.get(f"{BASE}/trade/bazaar", timeout=30).url)
        print("  фильтры:", list(dict.fromkeys(re.findall(r'href="([^"]*filter\w*Link[^"]*)"', b)))[:8])
        print("  'Выставить ресурсы':", "Выставить ресурсы" in b)

        # витрина клана
        gid = "16675"
        v = s.get(f"{BASE}/guild/public/store", timeout=30).text
        vt = " ".join(text_of(v).split())
        print("  ВИТРИНА:", vt[:260])
        print("  ссылки витрины:", list(dict.fromkeys(re.findall(r'href="([^"]+)"', v)))[:14])
        for key in ("Выставить", "Продать", "Добавить", "Отправить", "цена", "Цена"):
            if key in vt:
                i = vt.find(key)
                print(f"   [{key}]:", vt[max(0, i - 80):i + 160])

        # страница одной вещи: есть ли «выставить на продажу»
        rack = s.get(f"{BASE}/user/rack", timeout=30).text
        ids = re.findall(r'href="\.\./item/id/(\d+)"', rack)
        if ids:
            it = s.get(f"{BASE}/item/id/{ids[0]}", timeout=30).text
            itt = " ".join(text_of(it).split())
            print("  ВЕЩЬ:", itt[:300])
            print("  ссылки вещи:", list(dict.fromkeys(re.findall(r'href="([^"]+)"', it)))[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
