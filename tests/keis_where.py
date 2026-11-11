"""Диагностика keis: где реально есть кнопка входа в бой."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

URLS = [
    ("башня", "https://barbars.ru/game/towers"),
    ("карта башен", "https://barbars.ru/game/towers/map"),
    ("арена", "https://barbars.ru/game/arena"),
    ("дуэли", "https://barbars.ru/game/duel"),
    ("выживание", "https://barbars.ru/game/survival"),
    ("битва героев", "https://barbars.ru/game/battle"),
    ("дракон", "https://barbars.ru/game/dragonDungeon"),
    ("святилище", "https://barbars.ru/game/greatBoss"),
    ("подземелья", "https://barbars.ru/game/dungeons"),
    ("поход", "https://barbars.ru/journey"),
    ("вещи", "https://barbars.ru/user/rack"),
    ("сундук", "https://barbars.ru/user/store"),
]


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    for label, url in URLS:
        r = s.get(url, timeout=30)
        html = r.text
        text = " ".join(text_of(html).split())
        # ссылки, похожие на кнопки входа в бой
        btns = set()
        for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
            label_txt = " ".join(text_of(m.group(2)).split())
            href = m.group(1)
            if re.search(r"(fight|attack|damage|battle|start|enter|duel|go)", href, re.I) or \
               re.search(r"(Бить|Начать|Войти|Вызвать|Сражаться|Атаковать)", label_txt, re.I):
                btns.add(f"{label_txt[:30]} -> {href.split('wicket:interface')[-1][:70]}")
        print(f"\n=== {label} ({url.split('.ru')[-1]}) ===")
        print("  заголовок:", text[:110])
        for b in list(btns)[:8]:
            print("   *", b)
        if not btns:
            print("   (кнопок входа не найдено)")
        if "autoCrack" in html:
            print("   autoCrack-ссылки:", set(re.findall(r"autoCrack\w*Link", html)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
