"""Живая проверка новых методов: поля сражений, свитки, умения за очки."""
from __future__ import annotations

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


def make(cfg_file: str, profile: str) -> Game:
    user, password = creds(cfg_file)
    f = DESKTOP / cfg_file
    g = Game({"base_url": BASE, "profile_dir": profile, "headless": True,
              "auth": {"credentials_file": str(f)}, "humanize": {"enabled": False}}, profile)
    g.start()
    g.goto(f"{BASE}/login")
    g.p.fill("input[name='login']", user, timeout=8000)
    g.p.fill("input[name='password']", password, timeout=8000)
    g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
    g.p.wait_for_load_state("domcontentloaded", timeout=20000)
    assert g.is_authenticated()
    return g


def main() -> int:
    g = make("barbars-firewhite-credentials.txt", "profile-probe-arena")
    try:
        print("ПОЛЯ СРАЖЕНИЙ (firewhite):", {k: v for k, v in g.battlefields_state().items() if k != "text"})
        print("СВИТКИ (firewhite):", g.scroll_items())
    finally:
        g.close()

    g2 = make("barbars-agentcredentials.txt", "profile-probe-keis")
    try:
        print("ПОЛЯ СРАЖЕНИЙ (keis):", {k: v for k, v in g2.battlefields_state().items() if k != "text"})
        data = g2.ability_options("52")
        print("ОЧКИ ПОЛЕЙ (keis):", data["points"])
        for opt in data["options"]:
            print("   ", opt)
        print("СВИТКИ (keis):", g2.scroll_items())
    finally:
        g2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
