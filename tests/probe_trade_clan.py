"""Проверка: (1) где продаются вещи, (2) клановое хранилище, (3) ранг в клане."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def links(html: str, pat: str) -> list[str]:
    return list(dict.fromkeys(re.findall(pat, html)))[:10]


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n======== {label} ========")

        # (1) торговля: что вообще можно продать
        for url in (f"{BASE}/market", f"{BASE}/trade"):
            h = s.get(url, timeout=30).text
            t = " ".join(text_of(h).split())
            print(f"  {url}: вкладки {links(h, r'href=\"([^\"]*(?:tab|market|trade)[^\"]*)\"')[:8]}")
            print("   текст:", t[:400])
            print("   ссылки продажи:", links(h, r'href="([^"]*(?:sell|Sell|lot|put|price)[^"]*)"')[:8])

        # (2) клановое хранилище
        home = s.get(f"{BASE}/", timeout=30).text
        gid = None
        m = re.search(r"guild/(\d+)", home) or re.search(r"guildId=(\d+)", home)
        if m:
            gid = m.group(1)
        if gid:
            st = s.get(f"{BASE}/guild/storage/0/{gid}", timeout=30)
            t = " ".join(text_of(st.text).split())
            print("  ХРАНИЛИЩЕ:", t[:300])
            print("   ссылки:", links(st.text, r'href="([^"]*storage[^"]*)"')[:8])
            print("   вещи/передача:", links(st.text, r'href="([^"]*(?:sendTo|item|put|add)[^"]*)"')[:8])
        else:
            print("  ХРАНИЛИЩЕ: клан не найден")

        # (3) ранг в клане
        if gid:
            gh = s.get(f"{BASE}/guild/{gid}", timeout=30)
            t = " ".join(text_of(gh.text).split())
            for key in ("Ранг", "ранг", "Уровень клана", "Стаж", "новичок", "ветеран", "офицер", "генерал"):
                for mm in list(re.finditer(rf"[^.]{{0,60}}{key}[^.]{{0,80}}", t))[:2]:
                    print("   КЛАН:", mm.group(0).strip()[:160])
            print("   ссылки клана:", links(gh.text, r'href="([^"]*(?:rank|store|storage|member)[^"]*)"')[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
