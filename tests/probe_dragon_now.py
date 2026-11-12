"""Сейчас в игре: убито ли драконов кланом и жива ли мифическая пещера."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
GUILD = "16675"


def main() -> int:
    cred = DESKTOP / "barbars-agentcredentials.txt"
    lines = [l.strip().lstrip("\ufeff") for l in cred.read_text(encoding="utf-8-sig").splitlines()]
    user, password = [l for l in lines if l][:2]
    g = Game({"base_url": BASE, "profile_dir": "profile-probe-dragon-now", "headless": True,
              "auth": {"credentials_file": str(cred)},
              "humanize": {"enabled": False}}, "profile-probe-dragon-now")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto(f"/guild/achievements/0/{GUILD}")
        text = " ".join(g.body_text().split())
        print("===== ДОСТИЖЕНИЯ КЛАНА =====")
        for m in re.finditer(r"[^ ]*Дракон[^ ]*", text):
            start = max(0, m.start() - 120)
            print("...", text[start:m.end() + 160], "...")
        idx = text.find("Дракон")
        if idx >= 0:
            print("ФРАГМЕНТ:", text[max(0, idx - 200):idx + 400])

        g.goto("/game/dragonDungeon")
        room = " ".join(g.body_text().split())
        print()
        print("===== ПЕЩЕРА ДРАКОНА =====")
        print(room[:500])
    finally:
        try:
            g.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
