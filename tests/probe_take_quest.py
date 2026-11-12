"""Взятие кланового задания: сколько кнопок и что происходит при клике."""
from __future__ import annotations

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
    g = Game({"base_url": BASE, "profile_dir": "profile-takeq", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, "profile-takeq")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        g.goto(BASE + "/user")
        g.hero()
        print("guild_id:", g.guild_id, "hero_id:", g.hero_id)
        g.goto(f"{BASE}/guild/quests/0/{g.guild_id}")
        loc = g.p.locator("a:has-text('Взять задание'), button:has-text('Взять задание')")
        print("кнопок «Взять задание»:", loc.count())
        for i in range(loc.count()):
            try:
                print("  ", i, repr(loc.nth(i).inner_text().strip()),
                      loc.nth(i).get_attribute("href"))
            except Exception as exc:  # noqa: BLE001
                print("  ", i, "ошибка", exc)
        print("url страницы:", g.p.url)
        print("текст (начало):", " ".join(g.body_text().split())[:300])
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
