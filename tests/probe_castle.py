"""Разметка кнопок входа на странице замка: где указана цена."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    f = DESKTOP / "barbars-agentcredentials.txt"
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": "profile-castle", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, "profile-castle")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        g.goto(BASE + "/castle/6")
        html = g.p.content()
        for kw in ("Войти в замок", "money_gold", "money_silver"):
            i = html.find(kw)
            print(f"=== {kw} @ {i}")
            if i >= 0:
                print(re.sub(r"\s+", " ", html[max(0, i - 900):i + 900]))
            print()
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
