"""Ресурсы героя и цены прокачки: что можно вложить в параметры.

Печатает: золото/серебро/железо/мифрил, список параметров с ценой и валютой,
а также цену следующего уровня мастерства.
"""
from __future__ import annotations

import json
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


def show(g: Game, who: str) -> None:
    st = g.status()
    print(f"===== {who} =====")
    print(f"  золото={st.gold} серебро={st.silver} железо={st.iron} "
          f"мифрил={st.mifril} бутылки={st.bottles} hp={st.hp} энергия={st.energy}")
    try:
        mcost = g.mastery_level_cost()
    except Exception as e:  # noqa: BLE001
        mcost = {"ошибка": str(e)}
    print("  цена мастерства:", mcost)
    try:
        params = g.master_upgrade_options()
    except Exception as e:  # noqa: BLE001
        params = [{"ошибка": str(e)}]
    for p in params:
        print("  ", json.dumps(p, ensure_ascii=False))


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    data = creds(ACC[who])
    if not data:
        print(f"нет учётных данных для {who}")
        return 1
    user, password = data
    g = Game({"base_url": BASE, "profile_dir": f"profile-res-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / ACC[who])},
              "humanize": {"enabled": False}}, f"profile-res-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"
        g.goto(BASE + "/")
        show(g, who)
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
