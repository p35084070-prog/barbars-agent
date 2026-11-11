"""Сколько бесплатных боёв осталось у каждого аккаунта (/fightmore)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    for label, filename in (("keis", "barbars-agentcredentials.txt"),
                            ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / filename).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        home = " ".join(text_of(s.get("https://barbars.ru/", timeout=30).text).split())
        fightmore = " ".join(text_of(s.get("https://barbars.ru/fightmore", timeout=30).text).split())
        m = re.search(r"провести\s*(\d+)\s*бо(?:я|и|ев)\s*в подземельях\s*и\s*(\d+)\s*бо(?:я|и|ев)\s*в дуэлях", fightmore)
        left = f"подземелья={m.group(1)} дуэли={m.group(2)}" if m else "не найдено"
        cooldowns = re.findall(r"(Подземелья|Дуэли)\s*откроются через ([^.]+)\.", home)
        print(f"{label}: {left}; " + "; ".join(f"{a}: {b}" for a, b in cooldowns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
