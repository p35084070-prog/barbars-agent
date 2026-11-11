"""Валюта улучшений: мастерство (/user/master) и кузнец (/trade/smith)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login  # noqa: E402


def near(html, needle, before=250, after=250):
    i = html.find(needle)
    if i < 0:
        return "(не найдено)"
    return " ".join(html[max(0, i - before):i + after].split())


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    m = s.get("https://barbars.ru/user/master", timeout=30).text
    print("=== мастерство ===")
    print("  иконки денег:", sorted(set(re.findall(r"money_\w+\.png", m))))
    print("  вокруг «Повысить за»:", near(m, "Повысить за", 250, 350)[:500])
    print("  вокруг upLink:", near(m, "moreParamsPanel:strength", 350, 250)[:600])

    k = s.get("https://barbars.ru/trade/smith", timeout=30).text
    print("\n=== кузнец ===")
    print("  иконки денег:", sorted(set(re.findall(r"money_\w+\.png", k))))
    print("  вокруг «Требуется: Шлем»:", near(k, "Требуется: Шлем", 450, 450)[:800])
    print("  вокруг «повысить уровень»:", near(k, "повысить уровень", 500, 400)[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
