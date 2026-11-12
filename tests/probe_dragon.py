"""Разведка клановых боссов: мифический дракон и его требования.

Заходит под keis (лидер клана «Слепые ТИТАНЫ») и вытаскивает со страниц:
текст, ссылки и параметры боя (мощность отряда, HP босса, лечение).
"""
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

PAGES = [
    ("dragonDungeon", "/game/dragonDungeon"),
    ("dungeons", "/game/dungeons"),
    ("greatBoss", "/game/greatBoss"),
    ("journey", "/journey"),
    ("guild", "/guild/16675"),
]


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

        for name, path in PAGES:
            g.goto(path)
            html = g.p.content()
            text = " ".join(g.body_text().split())
            (RAW / f"dragon-{name}.html").write_text(html, encoding="utf-8")
            print(f"\n========== {name} ({path}) ==========")
            print(text[:2500])
            print("--- ссылки ---")
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
                label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
                href = m.group(1)
                if any(k in (label + " " + href).lower() for k in (
                        "start", "ready", "combat", "dragon", "boss", "леч", "мощн",
                        "power", "heal", "raid", "journey", "поход", "начать", "бой")):
                    print(f"   {label[:60]} -> {href[:90]}")
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
