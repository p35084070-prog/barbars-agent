"""Журнал клана, достижения, статы и список боссов — ищем данные про убийства драконов."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def main() -> int:
    user, password = creds("barbars-agentcredentials.txt")
    g = Game({"base_url": BASE, "profile_dir": "profile-probe-dragon", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / "barbars-agentcredentials.txt")},
              "humanize": {"enabled": False}}, "profile-probe-dragon")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        for name, path in (
            ("journal", "/guild/journal/0/16675"),
            ("achievements", "/guild/achievements/0/16675"),
            ("stat", "/guild/stat/0/16675"),
            ("skill", "/guild/skill"),
            ("arenas", "/guild/arenas/0/16675"),
            ("dungeons-clan", "/game/dungeons/1/2"),
            ("help-games", "/help/0/games"),
        ):
            g.goto(path)
            text = " ".join(g.body_text().split())
            print(f"\n========== {name} ({path}) ==========")
            print(text[:2200])
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
