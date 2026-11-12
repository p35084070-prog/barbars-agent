"""Протокол зала босса: что значит «Я готов!», кто кого видит, когда начинается бой.

Заходим в зал Мифического дракона, жмём «Я готов!» (НЕ «Начать бой!») и смотрим:
- кто в зале и готов ли (check_green / check_gray),
- стартует ли бой сам, когда в зале есть готовые герои.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
RAW = Path(__file__).resolve().parent / "raw"
RAW.mkdir(parents=True, exist_ok=True)

ACCOUNTS = {
    "firewhite": "barbars-firewhite-credentials.txt",
    "keis": "barbars-agentcredentials.txt",
}


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def room_state(g: Game) -> str:
    html = g.p.content()
    text = " ".join(g.body_text().split())
    m = re.search(r"(Кто здесь[^<]*)", html)
    block = ""
    if m:
        start = html.find("Кто здесь")
        block = html[start:start + 1200]
    ready = block.count("check_green")
    gray = block.count("check_gray")
    names = re.findall(r'user/id/(\d+)"><span>([^<]+)</span>', block)
    hp = re.search(r"dragon_mif\.png[^>]*>\s*<span>(\d+)%", html)
    return (
        f"HP={hp.group(1) if hp else '?'}% | готовых={ready} неготовых={gray} | "
        f"герои={[n[1] for n in names]} | {text[:200]}"
    )


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    cfg_file = ACCOUNTS[who]
    user, password = creds(cfg_file)
    g = Game({"base_url": BASE, "profile_dir": f"profile-probe-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / cfg_file)},
              "humanize": {"enabled": False}}, f"profile-probe-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto("/game/dragonDungeon")
        print(f"[{who}] 1. зал: {room_state(g)}")

        try:
            g.click_text("Я готов!")
            print(f"[{who}] нажали «Я готов!»")
        except Exception as exc:
            print(f"[{who}] «Я готов!» не нажалась: {exc}")
        time.sleep(3)
        print(f"[{who}] 2. зал: {room_state(g)}")

        for i in range(6):
            time.sleep(15)
            g.goto("/game/dragonDungeon")
            state = room_state(g)
            print(f"[{who}] 3. +{(i + 1) * 15}с: {state}")
            if "Бить дракона" in g.body_text() or "Вход закрыт" in g.body_text():
                print(f"[{who}] бой пошёл!")
                break
        (RAW / f"room-{who}.html").write_text(g.p.content(), encoding="utf-8")
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
