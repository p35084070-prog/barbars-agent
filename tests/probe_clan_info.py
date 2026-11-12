"""Разведка: журнал клана, достижения, справка — где игра пишет про силу отряда и лечение."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
RAW = Path(__file__).resolve().parent / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def main() -> int:
    user, password = creds("barbars-agentcredentials.txt")
    g = Game({"base_url": BASE, "profile_dir": "profile-probe-dragon", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / "barbars-agentcredentials.txt")},
              "humanize": {"enabled": False}}, "profile-probe-dragon")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        # 1. все ссылки клана — ищем журнал и достижения
        g.goto("/guild/16675")
        html = g.p.content()
        print("========== ССЫЛКИ КЛАНА ==========")
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
            if label:
                print(f"   {label[:45]:45} -> {m.group(1)[:80]}")

        # 2. журнал клана, достижения, справка
        for name, path in (("journal", "/guild/journal/16675"),
                           ("achievements", "/guild/achievements/16675"),
                           ("quests", "/guild/quests/0/16675"),
                           ("help-clans", "/help/0/clans"),
                           ("help-gameplay", "/help/0/gameplay")):
            g.goto(path)
            text = " ".join(g.body_text().split())
            print(f"\n========== {name} ({path}) ==========")
            print(text[:1800])
            links = re.findall(r'href="([^"]+)"', g.p.content())
            interesting = [l for l in links if any(k in l.lower() for k in (
                "journal", "achievement", "boss", "dragon", "raid", "quest"))]
            if interesting:
                print("--- ссылки:", ", ".join(sorted(set(interesting))[:20]))
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
