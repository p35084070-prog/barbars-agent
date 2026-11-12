"""Бонус мастерства и баланс — главное, что растёт от прокачки железом."""
from __future__ import annotations

import re
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


def show(who: str) -> None:
    f = DESKTOP / ACC[who]
    if not f.exists():
        print(f"{who}: нет кредов")
        return
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": f"profile-mast-{who}", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, f"profile-mast-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto(BASE + "/user")
        st = g.status()
        print(f"{who}: железо={st.iron} мифрил={st.mifril} серебро={st.silver} "
              f"золото={st.gold} бутылки={st.bottles} hp={st.hp}")

        g.goto(BASE + "/user/master")
        text = " ".join(g.body_text().split())
        m = re.search(r"бонус\s*\+(\d+)\s*%", text)
        lvl = re.search(r"Твой уровень:\s*(\d+)", text)
        print(f"  мастерство: уровень={lvl.group(1) if lvl else '?'} "
              f"бонус=+{m.group(1) if m else '?'}%")
        print("  цена:", g.mastery_level_cost())
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    for who in (sys.argv[1:] or ["firewhite", "keis"]):
        show(who)
    return 0


if __name__ == "__main__":
    sys.exit(main())
