"""Эксперимент: что происходит с железом при клике «Получить подарок» в колодце.

Снимаем баланс до и после клика по getDailyGiftLink.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
ACC = {
    "keis": "barbars-agentcredentials.txt",
    "firewhite": "barbars-firewhite-credentials.txt",
}


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    f = DESKTOP / ACC[who]
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": f"profile-gift-{who}", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, f"profile-gift-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto(BASE + "/trade/well")
        before = g.status()
        print(f"ДО: железо={before.iron} золото={before.gold} серебро={before.silver}")
        ok = g.click_href("getDailyGiftLink")
        print("клик по getDailyGiftLink:", ok)
        g.goto(BASE + "/user")
        after = g.status()
        print(f"ПОСЛЕ: железо={after.iron} золото={after.gold} серебро={after.silver}")
        print("разница по железу:", (before.iron or 0) - (after.iron or 0))
        print("разница по золоту:", (before.gold or 0) - (after.gold or 0))
        print("разница по серебру:", (before.silver or 0) - (after.silver or 0))
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
