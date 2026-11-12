"""Читает status() на странице /user — так же, как это делает цикл агента."""
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
    g = Game({"base_url": BASE, "profile_dir": f"profile-st-{who}", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, f"profile-st-{who}")
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
        print(f"{who} на /user: железо={st.iron} мифрил={st.mifril} серебро={st.silver} "
              f"золото={st.gold} бутылки={st.bottles} hp={st.hp}")
        # сколько вообще элементов с иконкой железа и что после них
        loc = g.p.locator("img[src*='ironbar.png']")
        print("иконок железа на странице:", loc.count())
        print("html вокруг иконки:",
              g.p.content()[max(0, g.p.content().find("ironbar.png") - 200):
                            g.p.content().find("ironbar.png") + 300].replace("\n", " "))
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
