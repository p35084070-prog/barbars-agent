"""Стоимость ремонта снаряжения — чтобы правильно держать запас железа."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars import pages  # noqa: E402
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
    if not f.exists():
        print("нет кредов")
        return 1
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": f"profile-rep-{who}", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, f"profile-rep-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        g.goto(BASE + "/user")
        hero = g.hero()
        hero_id = g.hero_id
        print("hero_id:", hero_id, "hp:", hero.max_hp)
        g.goto(f"{BASE}/user/body/id/{hero_id}")
        print("repair_info:", pages.repair_info(g))
        print("железо:", g.status().iron)
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
