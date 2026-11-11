"""keis: валюта похода, локация «Курган» (есть ли «Бить врагов»), панель готовности босса."""
from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    j = s.get("https://barbars.ru/journey", timeout=30).text
    i = j.find("buy8Link")
    chunk = j[max(0, i - 100):i + 400]
    print("=== поход: иконка валюты ===")
    print(" ", " ".join(chunk.split())[:500])

    print("\n=== башня: карта -> Курган ===")
    t = s.get("https://barbars.ru/game/towers/map", timeout=30).text
    for idx, name in ((0, "Курган"), (8, "Долина Сражений")):
        m = re.search(rf"href=\"([^\"]*nearLocation:{idx}:locationLink[^\"]*)\"", t)
        if not m:
            print(f"  {name}: ссылка не найдена")
            continue
        url = urljoin("https://barbars.ru/game/towers/map", m.group(1).replace("&amp;", "&"))
        page = s.get(url, timeout=30)
        txt = " ".join(text_of(page.text).split())
        print(f"  {name}: damage={len(re.findall('damageRandomEnemyLink', page.text))} "
              f"'Бить'={page.text.count('Бить')} | {txt[:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
