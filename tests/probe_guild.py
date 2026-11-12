"""Баланс хранилища клана: сколько железа вложено."""
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
    f = DESKTOP / "barbars-agentcredentials.txt"
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": "profile-guild", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, "profile-guild")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        g.goto(BASE + "/user")
        gid = g.guild_id
        print("guild_id:", gid)
        g.goto(f"{BASE}/guild/{gid}")
        text = " ".join(g.body_text().split())
        print("текст:", text[:1200])
        html = g.p.content()
        for icon, amount in re.findall(
                r'icons/(money_gold|money_silver|ironbar|mifrilbar)\.png[^>]*>\s*<span[^>]*>([\d.,]+[KkMm]?)</span>',
                html):
            print(f"  {icon} = {amount}")
        print()
        print("--- ссылки хранилища ---")
        for link in g.p.locator("a").all():
            try:
                text2 = link.inner_text().strip().replace("\n", " ")
                href = link.get_attribute("href") or ""
            except Exception:  # noqa: BLE001
                continue
            if not text2:
                continue
            if re.search(r"желез|вклад|внести|полож|донат|хранилищ", text2 + href, re.IGNORECASE):
                print(f"  {text2[:60]!r} -> {href[:110]}")
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
