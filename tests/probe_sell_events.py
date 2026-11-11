"""Проверка: (1) ссылки разбора в рюкзаке, (2) можно ли продать шмотку, (3) клановые события."""
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

        rack = s.get(f"{BASE}/user/rack", timeout=30).text
        txt = " ".join(text_of(rack).split())
        m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", txt)
        print("  рюкзак:", m.group(0) if m else "?")
        for key in ("crackLink", "crackAllIronLink", "wearLink", "toStoreLink", "items:"):
            print(f"   {key}: {len(re.findall(key, rack))}")
        # выведем блоки предметов как есть (урезанно)
        chunks = rack.split('<div class="hr"></div>')
        found = 0
        for chunk in chunks:
            if "items:" not in chunk:
                continue
            found += 1
            if found <= 4:
                names = re.findall(r"href=\"\.\./item/id/\d+\"><span>([^<]+)</span>", chunk)
                hrefs = re.findall(r'href="([^"]*items:\d+:[^"]*)"', chunk)
                print(f"    блок: {names} | {hrefs}")
        print("   блоков с items:", found)

        # (2) продажа шмоток: ссылки на продажу где-либо
        for page, name in (("/user/rack", "рюкзак"), ("/user/store", "сундук"), ("/market", "аукцион")):
            try:
                h = s.get(BASE + page, timeout=30).text
            except Exception as exc:
                print(f"   {name}: ошибка {exc}")
                continue
            sale = sorted(set(re.findall(r'href="([^"]*(?:sell|Sell|продаж)[^"]*)"', h)))
            print(f"   {name}: sell-ссылки {sale[:6]}; текст про продажу: "
                  f"{[w for w in re.findall(r'[Пп]родать[^,.<]{0,40}', text_of(h))][:4]}")

        # (3) клановые события: боссы и замки
        for url in ("https://barbars.ru/game/dragonDungeon", "https://barbars.ru/game/greatBoss"):
            h = s.get(url, timeout=30).text
            ht = " ".join(text_of(h).split())
            links = sorted(set(re.findall(r'href="([^"]*(?:startCombatLink|readyLink|bossLink|fightLink)[^"]*)"', h)))
            print(f"   {url.split('/')[-1]}: {ht[:120]} | ссылки {links[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
