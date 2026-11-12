"""Сколько стоит вход в каждое фарм-событие: золото/серебро у кнопок."""
from __future__ import annotations

import json
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

EVENTS = [
    ("Арена", "/game/arena"),
    ("Турниры", "/game/contests"),
    ("Выживание", "/game/survival"),
    ("Подземелья", "/game/dungeons"),
    ("Великие битвы", "/games/greats"),
    ("Замок: Зеркало боли", "/castle/6"),
    ("Замок: Колыбель жизни", "/castle/8"),
    ("Битва героев", "/game/battle"),
]


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    f = DESKTOP / ACC[who]
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": f"profile-price-{who}", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, f"profile-price-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        for name, path in EVENTS:
            g.goto(BASE + path)
            html = g.p.content()
            st = g.status()
            prices = []
            for icon, amount in re.findall(
                    r'icons/(money_gold|money_silver|ironbar)\.png[^>]*>\s*<span[^>]*>([\d.,]+[KkMm]?)</span>',
                    html):
                prices.append(f"{icon}={amount}")
            buttons = []
            for link in g.p.locator("a").all():
                try:
                    text = link.inner_text().strip().replace("\n", " ")
                except Exception:  # noqa: BLE001
                    continue
                if re.search(r"^(Начать бой|Войти|Встать в очередь|Участвовать|Играть|Бить|Атаковать)",
                             text):
                    buttons.append(text[:70])
            print(f"--- {name} ({path})")
            print(f"    золото={st.gold} серебро={st.silver} железо={st.iron}")
            print(f"    цены на странице: {prices[:8]}")
            print(f"    кнопки: {buttons[:6]}")
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
