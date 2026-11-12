"""Гайды по мифическому дракону: справка игры и форум (только чтение)."""
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

        # 1. все темы справки
        g.goto("/help/0/games")
        html = g.p.content()
        print("========== ТЕМЫ СПРАВКИ ==========")
        topics = []
        for m in re.finditer(r'<a[^>]+href="([^"]*help/0/[^"]+)"[^>]*>(.*?)</a>', html, re.S):
            label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
            if label and (label, m.group(1)) not in topics:
                topics.append((label, m.group(1)))
        for label, href in topics:
            print(f"   {label[:45]:45} -> {href}")

        # 2. страница справки про пещеры
        for label, href in topics:
            if any(k in label.lower() for k in ("пещер", "дракон", "сраж", "помощь")):
                g.goto(href if href.startswith("http") else BASE + "/" + href.lstrip("./"))
                text = " ".join(g.body_text().split())
                print(f"\n========== СПРАВКА: {label} ({href}) ==========")
                print(text[:2500])

        # 3. форум: ищем темы про дракона
        g.goto("/forum/main")
        html = g.p.content()
        print("\n========== ФОРУМ: разделы ==========")
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
            if label and len(label) < 60 and any(k in label.lower() for k in (
                    "пещер", "дракон", "босс", "клан", "рейд", "помощ", "вопрос", "обсуж")):
                print(f"   {label[:50]:50} -> {m.group(1)[:80]}")
        # поиск по форуму, если есть форма
        try:
            g.p.fill("input[name='text']", "дракон", timeout=5000)
            g.p.click("input[type='submit']", timeout=8000)
            g.p.wait_for_load_state("domcontentloaded", timeout=20000)
            text = " ".join(g.body_text().split())
            print("\n========== ПОИСК ПО ФОРУМУ: дракон ==========")
            print(text[:1500])
        except Exception as exc:
            print("поиск по форуму не удался:", exc)
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
