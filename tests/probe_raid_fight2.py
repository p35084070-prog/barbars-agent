"""Точный замер попытки боя с мифическим драконом.

Бьём непрерывно и пишем: сколько длится попытка (часы на странице), сколько
процентов HP сняли, наш HP, что было в боевом журнале и когда попытка кончилась.
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
ACCOUNTS = {
    "firewhite": "barbars-firewhite-credentials.txt",
    "keis": "barbars-agentcredentials.txt",
}


def creds(name: str):
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def clock_of(html: str) -> str:
    m = re.search(r'clock\.png"[^>]*>\s*<span[^>]*>(\d+:\d+:\d+)</span>', html)
    return m.group(1) if m else "?"


def boss_hp(html: str) -> str:
    m = re.search(r'dragon_mif\.png"[^>]*>\s*<span>(\d+)%', html)
    return m.group(1) if m else "?"


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

        # ждём открытия пещеры
        for _ in range(40):
            g.goto("/game/dragonDungeon")
            text = " ".join(g.body_text().split())
            if "Вход закрыт" not in text:
                print(f"[{who}] пещера открыта")
                break
            m = re.search(r"Откроется через[:\s]*([\d:]+)", text)
            print(f"[{who}] закрыто, откроется через {m.group(1) if m else '—'}")
            time.sleep(20)
        else:
            print(f"[{who}] пещера не открылась")
            return 1

        g.click_text("Начать бой!")
        time.sleep(2)
        print(f"[{who}] начали бой")

        last_log = ""
        for i in range(120):
            html = g.p.content()
            body = " ".join(g.body_text().split())
            if "Бить дракона" not in body:
                print(f"[{who}] бой закончился на итерации {i}: {body[:180]}")
                break
            link = g.p.locator("a:has-text('Бить дракона')").first
            try:
                link.click(timeout=8000)
            except Exception as exc:
                print(f"[{who}] клик не удался: {exc}")
                break
            time.sleep(0.4)
            html = g.p.content()
            body = " ".join(g.body_text().split())
            logs = re.findall(r"Ты [^.]{0,60}", body)
            new = [x for x in logs if x not in last_log]
            last_log = " ".join(logs)
            hp = re.search(r"life\.png[^>]*>\s*<span>(\d+)</span>", html)
            print(f"[{who}] удар {i + 1}: часы={clock_of(html)} HPбосса={boss_hp(html)}% "
                  f"нашеHP={hp.group(1) if hp else '?'} | {new[-1] if new else ''}")
    finally:
        try:
            g.click_text("Покинуть бой")
        except Exception:
            pass
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
