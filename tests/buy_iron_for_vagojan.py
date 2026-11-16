"""Покупка железа для vagojan через цепочку: его золото -> keis -> аукцион -> почта.

Шаг 1: vagojan (ОК-канал) переводит золото keis по почте.
Шаг 2: keis (barbars.ru) покупает лот железа на аукционе ресурсов.
Шаг 3: keis отправляет купленное железо vagojan по почте.

Запуск: python tests\buy_iron_for_vagojan.py [gold] [lots]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from barbars.ok_channel import OkGame  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
KEIS_ID = "905853"
VAGOJAN_ID = "1286381"


def ok_login(gold_to_send: int) -> tuple[OkGame, str]:
    config = json.loads((ROOT / "config-ok.json").read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = OkGame(config, ROOT / "profile-ok-gold2keis")
    game.start(headless=True)
    if not game.ensure_login(timeout_sec=120):
        raise SystemExit("не удалось войти через ОК")
    game.goto(f"{BASE}/user")
    before = game.status()
    print("vagojan до перевода:", before)
    ok = game.send_money_to(KEIS_ID, gold=gold_to_send, silver=0)
    print(f"перевод {gold_to_send} зол -> keis: {ok}")
    game.goto(f"{BASE}/user")
    after = game.status()
    print("vagojan после перевода:", after)
    return game, f"{before} -> {after}"


def keis_login():
    f = DESKTOP / "barbars-agentcredentials.txt"
    lines = [l.strip() for l in f.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    prof = "profile-buyiron-keis"
    g = Game({"base_url": BASE, "profile_dir": prof, "headless": True,
              "auth": {"credentials_file": str(f)}, "humanize": {"enabled": False}}, prof)
    g.start()
    g.goto(f"{BASE}/login")
    g.p.fill("input[name='login']", lines[0], timeout=8000)
    g.p.fill("input[name='password']", lines[1], timeout=8000)
    g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
    g.p.wait_for_load_state("domcontentloaded", timeout=20000)
    if not g.is_authenticated():
        raise SystemExit("не удалось войти под keis")
    return g


def main() -> int:
    gold = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    lots_n = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    game = None
    g = None
    try:
        game, delta = ok_login(gold)
    finally:
        if game:
            game.close()

    try:
        g = keis_login()
        g.goto(f"{BASE}/user")
        print("\nkeis после получения:", g.status())
        bought = 0
        total_qty = 0
        for _ in range(lots_n):
            res = g.buy_iron_with_gold(min_iron=10000, max_gold=gold)
            print("покупка:", res)
            if not res.get("ok"):
                break
            bought += 1
            total_qty += int(res.get("qty", 0))
        if bought:
            send = g.send_resources_to(VAGOJAN_ID, "iron", total_qty)
            print("отправка железа vagojan:", send)
        g.goto(f"{BASE}/user")
        print("keis после:", g.status())
    finally:
        if g:
            g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
