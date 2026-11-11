"""Диагностика keis: башня (бесплатные бои), рюкзак/сундук, авторазбор."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    towers = s.get("https://barbars.ru/game/towers", timeout=30)
    ttext = " ".join(text_of(towers.text).split())
    print("--- /game/towers ---")
    print(ttext[:600])
    print("locationLink:", len(re.findall(r"locationLink", towers.text)),
          "| damageRandomEnemyLink:", len(re.findall(r"damageRandomEnemyLink", towers.text)))

    rack = s.get("https://barbars.ru/user/rack", timeout=30)
    rtext = " ".join(text_of(rack.text).split())
    print("\n--- /user/rack ---")
    m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", rtext)
    print("рюкзак:", m.group(0) if m else "?")
    m = re.search(r"Открыть сундук\s*\((\d+)\s*/\s*(\d+)\)", rtext)
    print("сундук:", m.group(0) if m else "?")
    print("wearLink:", len(re.findall(r"wearLink", rack.text)),
          "| toStoreLink:", len(re.findall(r"toStoreLink", rack.text)),
          "| 'Лучше':", rack.text.count("Лучше"))

    body = s.get("https://barbars.ru/user/body/id/0", timeout=30)
    print("\n--- авторазбор (страница вещей) ---")
    for m in re.finditer(r"(autoCrack\w*Link)", body.text):
        pass
    print("autoCrack-ссылок на /user/body/id/0:", len(re.findall(r"autoCrack\w*Link", body.text)))

    home = " ".join(text_of(s.get("https://barbars.ru/", timeout=30).text).split())
    print("\n--- главная (бои) ---")
    for m in re.finditer(r"([^.]*остал\w*\s*\d+\s*бо\w*)", home):
        print("  ", m.group(1).strip()[:90])
    print("  кулдауны:", re.findall(r"(Подземелья|Дуэли)\s*откроются через ([^.]+)\.", home))
    return 0


if __name__ == "__main__":
    sys.exit(main())
