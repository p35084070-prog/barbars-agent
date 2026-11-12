"""Форма на странице колодца: какие поля отправляются вместе с подарком."""
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
    f = DESKTOP / "barbars-firewhite-credentials.txt"
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": "profile-well3", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, "profile-well3")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        g.goto(BASE + "/trade/well")
        html = g.p.content()
        print("--- формы ---")
        for m in re.finditer(r"<form[^>]*>", html):
            print("  ", m.group(0)[:200])
        print()
        print("--- input/select ---")
        for m in re.finditer(r"<(input|select)[^>]*>", html):
            print("  ", m.group(0)[:250])
        print()
        print("--- блок «Бонус удачи» и ссылки с ценами ---")
        i = html.find("Бонус удачи")
        print(re.sub(r"\s+", " ", html[max(0, i - 200):i + 2500]) if i >= 0 else "не найдено")
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
