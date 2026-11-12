"""Кнопки входа в режимы: как они выглядят в разметке (без клика)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
PAGES = [("/game/arena", "Арена"), ("/game/contests", "Турниры"),
         ("/game/survival", "Выживание"), ("/game/dungeons", "Подземелья")]


def main() -> int:
    f = DESKTOP / "barbars-agentcredentials.txt"
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": "profile-arena", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, "profile-arena")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        for path, name in PAGES:
            g.goto(BASE + path)
            html = g.p.content()
            text = " ".join(g.body_text().split())
            print(f"===== {name} ({path}) =====")
            print("текст:", text[:700])
            print("элементы с 'очередь/бой/вход':")
            for tag in ("a", "button", "span", "div"):
                loc = g.p.locator(f"{tag}:has-text('очередь')")
                n = loc.count()
                for i in range(min(n, 3)):
                    el = loc.nth(i)
                    try:
                        t = el.inner_text().strip().replace("\n", " ")
                    except Exception:  # noqa: BLE001
                        continue
                    if "очередь" not in t:
                        continue
                    print(f"   [{tag}] {t[:90]!r} visible={el.is_visible()}")
            for kw in ("Встать в очередь", "Начать бой", "Войти"):
                i = html.find(kw)
                if i >= 0:
                    print(f"   HTML[{kw}]:", re.sub(r"\s+", " ", html[max(0, i - 350):i + 350]))
                    break
            print()
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
