"""Параметры героя и ресурсы: сколько железа/золота/серебра и что можно прокачать.

Нужно, чтобы понять, есть ли смысл вкладывать железо в параметры (сила/здоровье)
перед рейдом на дракона.
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
ACC = {
    "keis": "barbars-agentcredentials.txt",
    "firewhite": "barbars-firewhite-credentials.txt",
}


def creds(name: str):
    f = DESKTOP / name
    if not f.exists():
        return None
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    data = creds(ACC[who])
    if not data:
        print(f"нет учётных данных для {who}")
        return 1
    user, password = data
    g = Game({"base_url": BASE, "profile_dir": f"profile-master-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / ACC[who])},
              "humanize": {"enabled": False}}, f"profile-master-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto(BASE + "/")
        text = " ".join(g.body_text().split())
        print(f"===== {who} =====")
        print("шапка:", text[:300])
        for label in ("железо", "мифрил", "золото", "серебро", "энергия"):
            for m in re.finditer(rf"{label}\s*[=:]?\s*([\d\s]+)", text):
                print(f"  {label}: {m.group(1).strip()[:20]}")
                break

        g.goto(BASE + "/user/master")
        html = g.p.content()
        t = " ".join(g.body_text().split())
        print()
        print("--- /user/master (длина текста %d) ---" % len(t))
        print(t[:1500])
        print()
        print("ссылки улучшения:", re.findall(r'href="([^"]*master[^"]*)"', html)[:20])
        print("числа с 'желез' рядом:", re.findall(r"([\d\s]{1,8})\s*(?:желез|железа)", t)[:20])
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
