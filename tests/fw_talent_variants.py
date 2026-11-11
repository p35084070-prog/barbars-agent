"""Ищем рабочий URL страницы таланта (прямая ссылка уводит на главную)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

VARIANTS = [
    "https://barbars.ru/user/talent/0/240",
    "https://barbars.ru/talent/0/240",
    "https://barbars.ru/user/talents/0/240",
    "https://barbars.ru/user/talent/240",
    "https://barbars.ru/user/stances/0/240",
    "https://barbars.ru/user/talent/0/240?wicket:bookmarkablePage=com.overmobile.combats.wicket.pages.TalentPage",
]


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    s.get("https://barbars.ru/user/stances", timeout=30)
    for url in VARIANTS:
        r = s.get(url, timeout=30, headers={"Referer": "https://barbars.ru/user/stances"})
        text = " ".join(text_of(r.text).split())
        hit = "выучить" in text.lower() or "изучить" in text.lower() or "Талант" in text
        print(f"{url}\n   -> {r.url} | есть таланты: {hit} | начало: {text[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
