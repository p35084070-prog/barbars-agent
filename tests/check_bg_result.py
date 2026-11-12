"""Проверка после боя на Полях сражений: боёв сегодня, очки полей.

Печатает разобранное состояние `/game/bg` для обоих героев: отсчёт до следующего
боя, число боёв сегодня, очки полей и ссылки для входа в бой.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars import pages  # noqa: E402
from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def make(cfg_file: str, profile: str) -> Game:
    user, password = creds(cfg_file)
    f = DESKTOP / cfg_file
    g = Game({"base_url": BASE, "profile_dir": profile, "headless": True,
              "auth": {"credentials_file": str(f)}, "humanize": {"enabled": False}}, profile)
    g.start()
    g.goto(f"{BASE}/login")
    g.p.fill("input[name='login']", user, timeout=8000)
    g.p.fill("input[name='password']", password, timeout=8000)
    g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
    g.p.wait_for_load_state("domcontentloaded", timeout=20000)
    assert g.is_authenticated()
    return g


def main() -> int:
    for cfg_file, profile, label in (
        ("barbars-firewhite-credentials.txt", "profile-probe-arena", "FIREWHITE"),
        ("barbars-agentcredentials.txt", "profile-probe-keis", "KEIS"),
    ):
        g = make(cfg_file, profile)
        try:
            g.goto(f"{BASE}/game/bg")
            html = g.p.content()
            text = g.body_text()
            info = pages.parse_battlefields(html, text)
            print(f"--- {label} ---")
            print("   отсчёт до боя:", info.get("countdown") or "—")
            print("   боёв сегодня:", info.get("fights_today"))
            print("   очки полей:", info.get("points"))
            print("   ссылок входа:", len(info.get("join") or []))
            for link in (info.get("join") or [])[:6]:
                print("     ", link.get("label", "")[:40], "->", str(link.get("href", ""))[:70])
            print("   текст:", " ".join(text.split())[:500])
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
                link_text = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
                if any(k in link_text for k in ("бой", "Штурм", "вступи", "начать", "Обновить", "В бой")):
                    print("   ссылка:", link_text[:50], "->", m.group(1)[:70])
        finally:
            g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
