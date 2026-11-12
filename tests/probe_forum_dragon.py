"""Форум: темы про мифического дракона и требования к отряду."""
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


def topics(g: Game, path: str, keyword: str = "") -> list[tuple[str, str]]:
    g.goto(path)
    html = g.p.content()
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]*topic/[^"]+)"[^>]*>(.*?)</a>', html, re.S):
        label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
        if label and (label, m.group(1)) not in out:
            out.append((label, m.group(1)))
    return out


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

        found: list[tuple[str, str]] = []
        for sub in ("/forum/subforum/0/78805", "/forum/subforum/0/4", "/forum/subforum/0/5"):
            print(f"\n========== РАЗДЕЛ {sub} ==========")
            for label, href in topics(g, sub)[:40]:
                print(f"   {label[:70]:70} -> {href[:60]}")
                if any(k in label.lower() for k in ("дракон", "пещер", "босс", "рейд", "клан")):
                    found.append((label, href))

        print("\n\n########## ТЕМЫ ПРО ДРАКОНА ##########")
        for label, href in found[:6]:
            g.goto(href if href.startswith("http") else BASE + "/" + href.lstrip("./"))
            text = " ".join(g.body_text().split())
            print(f"\n===== {label} =====")
            print(text[:2500])
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
