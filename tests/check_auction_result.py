"""Проверка итогов аукционов keis: почта (продажи) и кошелёк."""
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
    user, password = creds("barbars-agentcredentials.txt")
    f = DESKTOP / "barbars-agentcredentials.txt"
    g = Game({"base_url": BASE, "profile_dir": "profile-probe-keis", "headless": True,
              "auth": {"credentials_file": str(f)}, "humanize": {"enabled": False}}, "profile-probe-keis")
    g.start()
    g.goto(f"{BASE}/login")
    g.p.fill("input[name='login']", user, timeout=8000)
    g.p.fill("input[name='password']", password, timeout=8000)
    g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
    g.p.wait_for_load_state("domcontentloaded", timeout=20000)
    assert g.is_authenticated()
    try:
        g.goto(f"{BASE}/user/mail")
        text = " ".join(g.body_text().split())
        print("ПОЧТА:", text[:1200])
        g.take_mail()
        g._settle()
        g.goto(f"{BASE}/user")
        html = g.p.content()
        gold = re.findall(r"money_gold\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        silver = re.findall(r"money_silver\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        print("КОШЕЛЁК keis: золото=", gold[:1], "серебро=", silver[:1])
        # свои лоты на рынке
        g.goto(f"{BASE}/trade/auctions")
        link = g.p.locator("a:has-text('Аукцион вещей')")
        if link.count():
            link.first.click(timeout=8000)
            g._settle()
        html2 = g.p.content()
        print("лотов на рынке:", len(re.findall(r"trade/auction/item/id/\d+/pt/\d+", html2)))
        for m in re.finditer(r"item/id/(\d+)/pt/\d+\"[^>]*>(?:<span>)?([^<]{2,60})", html2):
            print("   лот:", m.group(2))
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
