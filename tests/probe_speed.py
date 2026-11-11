"""Разведка скорости прокачки: Мудрец (опыт за железо), подземелья, башня, задания."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " "))


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n======== {label} ========")

        # 1. Мудрец: опыт за железо
        html = s.get("https://barbars.ru/trade/ironmaster", timeout=30).text
        txt = strip(html)
        i = txt.find("Получить")
        print("МУДРЕЦ:", txt[i - 100:i + 900] if i >= 0 else "нет раздела")
        print("  иконки:", sorted(set(re.findall(r"icons/(money_\w+|ironbar|mifrilbar)\.png", html))))

        # 2. Главная: что доступно сейчас
        home = s.get("https://barbars.ru/", timeout=30)
        ht = strip(home.text)
        for pat in (r"Подземель\w+[^.]{0,120}", r"Дуэл\w+[^.]{0,120}", r"[Кк]олодец[^.]{0,100}",
                    r"участи\w+[^.]{0,80}", r"Поход[^.]{0,100}", r"Битва героев[^.]{0,100}"):
            for m in list(re.finditer(pat, ht))[:3]:
                print("  главная:", m.group(0).strip()[:150])

        # 3. Башня: какие локации и есть ли мобы
        tm = s.get("https://barbars.ru/game/towers/map", timeout=30)
        print("  БАШНЯ ссылки:", sorted(set(re.findall(r"towers?/(\d+)", tm.text)))[:20])
        for m in list(re.finditer(r"([^<>]{0,60}(?:уровень|ур\.?)[^<>]{0,40})", strip(tm.text)))[:12]:
            print("   ", m.group(1).strip()[:100])

        # 4. Клановые задания (Усиленная прокачка = 100M опыта)
        g = s.get("https://barbars.ru/", timeout=30).text
        m = re.search(r"guildId=(\d+)", g) or re.search(r"guild/(\d+)", g)
        if m:
            gid = m.group(1)
            q = s.get(f"https://barbars.ru/guild/quests/0/{gid}", timeout=30)
            qt = strip(q.text)
            j = qt.find("Усиленная")
            print("  ЗАДАНИЯ:", qt[j:j + 200] if j >= 0 else qt[:200])
            print("  ссылки заданий:", sorted(set(re.findall(r"quests?/[^:]*?:(\w+)Link", q.text)))[:10])
        else:
            print("  ЗАДАНИЯ: клан не найден на главной")
    return 0


if __name__ == "__main__":
    sys.exit(main())
