"""Мои лоты на рынке аукционов (что выставлено и по какой цене)."""
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
        g.goto(f"{BASE}/trade/auctions")
        link = g.p.locator("a:has-text('Аукцион вещей')")
        if link.count():
            link.first.click(timeout=8000)
            g._settle()
        mine = g.p.locator("a:has-text('Мои лоты')")
        print("найдено «Мои лоты»:", mine.count())
        if mine.count():
            mine.first.click(timeout=8000)
            g._settle()
        print("URL:", g.p.url)
        html = g.p.content()
        print("ТЕКСТ:", " ".join(g.body_text().split())[:1500])
        print("--- лоты ---")
        for chunk in html.split('<div class="hr"></div>'):
            m = re.search(r"trade/auction/item/id/(\d+)/pt/(\d+)", chunk)
            if not m:
                continue
            nm = re.search(r"item/id/\d+/pt/\d+\"[^>]*>(?:<span>)?([^<]{2,60})", chunk)
            price = re.findall(r"money_(gold|silver)\.png\"[^>]*>\s*<span>([\d.,]+)</span>", chunk)
            txt = " ".join(re.sub("<[^>]+>", " ", chunk).split())
            print(f"  id={m.group(1)} {nm.group(1) if nm else '?':<24} цены={price} | {txt[:120]}")
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
