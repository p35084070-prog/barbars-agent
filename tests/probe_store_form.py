"""Проба продажи вещи: форма цены на витрине и разделы аукциона вещей."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"


def creds(name: str) -> tuple[str, str]:
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    return lines[0], lines[1]


def main() -> int:
    user, password = creds("barbars-firewhite-credentials.txt")
    cfg = {"base_url": BASE, "profile_dir": "profile-probe-store", "headless": True,
           "auth": {"credentials_file": str(DESKTOP / "barbars-firewhite-credentials.txt")},
           "humanize": {"enabled": False}}
    g = Game(cfg, "profile-probe-store")
    try:
        g.start()
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        print("авторизован:", g.is_authenticated())

        # 1. Клик «на витрину» на дубликате (Перчатки Атланта уже на витрине — берём из рюкзака)
        g.goto(f"{BASE}/item/id/2092650299")
        print("\n--- страница вещи, есть 'на витрину':", "toPublicStoreLink" in g.p.content())
        # 2. Страницы аукциона вещей
        for url in (f"{BASE}/trade/auctions", f"{BASE}/trade/auctions/0/1",
                    f"{BASE}/trade/auction", f"{BASE}/trade/auction/items"):
            try:
                g.goto(url)
                txt = " ".join(g.body_text().split())
                print(f"\n### {url}\n{txt[:600]}")
                links = sorted(set(re.findall(r'href="([^"#]+)"', g.p.content())))
                for l in links:
                    if "trade" in l or "auction" in l:
                        print("   link:", l)
            except Exception as exc:
                print(f"\n### {url} ERROR {exc}")
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
