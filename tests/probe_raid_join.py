"""Вход в уже начавшийся бой: /game/dungeons → «Вернуться в бой»."""
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
ACCOUNTS = {
    "firewhite": "barbars-firewhite-credentials.txt",
    "keis": "barbars-agentcredentials.txt",
}


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


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

        g.goto("/game/dungeons")
        text = " ".join(g.body_text().split())
        print(f"[{who}] пещеры: {text[:260]}")
        if "Вернуться в бой" not in text:
            print(f"[{who}] «Вернуться в бой» нет")
            return 1
        g.click_text("Вернуться в бой")
        time.sleep(3)
        text = " ".join(g.body_text().split())
        print(f"[{who}] после клика: {text[:400]}")
        cs = g.combat()
        print(f"[{who}] удары: {cs.attack_links} | лечение: {cs.heal_links} | наше HP: {cs.our_hp}")
        if cs.attack_links or cs.heal_links:
            print("[+] мы в бою!")
            g.click_attack()
            time.sleep(2)
            print(f"[{who}] лог: {g.combat().log_lines[-3:]}")
    finally:
        try:
            g.click_text("Покинуть бой")
        except Exception:
            pass
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
