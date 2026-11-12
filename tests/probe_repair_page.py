"""Что именно предлагает игра на странице снаряжения: тексты про починку."""
from __future__ import annotations

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


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    f = DESKTOP / ACC[who]
    user, password = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()][:2]
    g = Game({"base_url": BASE, "profile_dir": f"profile-body-{who}", "headless": True,
              "auth": {"credentials_file": str(f)},
              "humanize": {"enabled": False}}, f"profile-body-{who}")
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
        hero_id = g.hero_id
        print("hero_id:", hero_id)
        g.goto(f"{BASE}/user/body/id/{hero_id}")
        print("url:", g.p.url)
        html = g.p.content()
        print("железо:", g.status().iron)
        print("repair_info:", __import__("barbars.pages", fromlist=["x"]).repair_info(g))
        print()
        print("--- все ссылки с 'очин' ---")
        for link in g.p.locator("a, button, input[type='submit']").all():
            try:
                text = link.inner_text().strip()
            except Exception:  # noqa: BLE001
                try:
                    text = (link.get_attribute("value") or "")
                except Exception:  # noqa: BLE001
                    continue
            if not text:
                continue
            if re.search(r"очин|чинить|ремонт|Почи", text, re.IGNORECASE):
                try:
                    href = link.get_attribute("href")
                except Exception:  # noqa: BLE001
                    href = None
                print(f"  [{link.evaluate('e => e.tagName')}] {text!r} href={href}")
        print()
        idx = html.lower().find("очин")
        print("фрагмент HTML:", re.sub(r"\s+", " ", html[max(0, idx - 400):idx + 400]))
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
