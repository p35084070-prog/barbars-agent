"""Боевые характеристики героев клана: сила, здоровье, энергия, регенерация."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
HEROES = [
    ("keis", "barbars-agentcredentials.txt", "905853"),
    ("firewhite", "barbars-firewhite-credentials.txt", "31389504"),
    ("vagojan", "barbars-agentcredentials.txt", "1286381"),
]


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def main() -> int:
    user, password = creds("barbars-agentcredentials.txt")
    g = Game({"base_url": BASE, "profile_dir": "profile-probe-stats", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / "barbars-agentcredentials.txt")},
              "humanize": {"enabled": False}}, "profile-probe-stats")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        for label, _, hero_id in HEROES:
            g.goto(f"/user/id/{hero_id}")
            text = " ".join(g.body_text().split())
            body = text.split("Мой герой", 1)[0]
            print(f"\n========== {label} (id {hero_id}) ==========")
            print(body[:700])
            m = re.search(r"(\d+)\s*ур", body)
            print("   уровень:", m.group(1) if m else "?")
            for stat in ("Сила", "Здоровье", "Энергия", "Регенерация", "Опыт", "Участие"):
                mm = re.search(rf"{stat}[^0-9]{{0,20}}([\d.,kM]+)", body)
                if mm:
                    print(f"   {stat}: {mm.group(1)}")
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
