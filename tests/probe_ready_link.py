"""Проверка: находится ли кнопка «Я готов!» и её href (только чтение, без клика)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    f = DESKTOP / "barbars-firewhite-credentials.txt"
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()][:2]
    g = Game({"base_url": BASE, "profile_dir": "profile-probe-ready", "headless": True,
              "auth": {"credentials_file": str(f)}, "humanize": {"enabled": False}}, "profile-probe-ready")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", lines[0], timeout=8000)
        g.p.fill("input[name='password']", lines[1], timeout=8000)
        g.p.click("input[type='submit']", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        g.goto(f"{BASE}/game/dragonDungeon")
        print("страница:", " ".join(g.body_text().split())[:300])
        found = 0
        for link in g.p.locator("a").all():
            try:
                text = " ".join((link.inner_text() or "").split())
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if "готов" in text or "readyLink" in href:
                found += 1
                print("НАЙДЕНО:", repr(text), "->", href[:90])
        print("всего ссылок про готовность:", found)
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
