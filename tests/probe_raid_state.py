"""Только чтение: состояние зала дракона и счётчики достижений клана (без кликов)."""
from __future__ import annotations

import re
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


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    cfg_file = "barbars-agentcredentials.txt" if who == "keis" else "barbars-firewhite-credentials.txt"
    user, password = creds(cfg_file)
    g = Game({"base_url": BASE, "profile_dir": f"profile-probe-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / cfg_file)},
              "humanize": {"enabled": False}}, f"profile-probe-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto("/game/dragonDungeon")
        html = g.p.content()
        text = " ".join(g.body_text().split())
        hp = re.search(r'dragon_mif\.png"[^>]*>\s*<span>(\d+)%', html)
        print(f"[{who}] зал: {text[:300]}")
        print(f"[{who}] HP босса: {hp.group(1) if hp else '?'}%")
        idx = html.find("Кто здесь")
        if idx >= 0:
            block = html[idx:idx + 1200]
            print(f"[{who}] в зале: {re.findall(r'user/id/\\d+.{0,40}?<span>([^<]+)</span>', block)}"
                  f" | готовых {block.count('check_green')}, неготовых {block.count('check_gray')}")

        g.goto("/guild/achievements/0/16675")
        ach = " ".join(g.body_text().split())
        m = re.search(r"Убито Драконов[:\s]*(\d+).{0,40}?рекорд по времени[:\s]*([\d:]+)", ach)
        print(f"[{who}] достижения: {ach[ach.find('Возраст'):ach.find('Трофеи')][:400]}")
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
