"""Этап 2 (firewhite): чистка дублей, обзор магазина, передача перчаток и золота keis."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
KEIS_ID = "905853"
GLOVES_DUP = "1968716698"   # Перчатки Атланта 25 — дубль (надеты другие)
BREAK_ITEMS = ["2093154603", "2093103808", "2093023478"]  # Амулет Ветерана 24, Секира Воина 20, Браслет Охотника 13
SETS = ["", "goliaf", "atlant", "veteran"]


def creds(name: str) -> tuple[str, str]:
    f = DESKTOP / name
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    return lines[0], lines[1]


def make(cfg_file: str, profile: str) -> Game:
    user, password = creds(cfg_file)
    cfg = {
        "base_url": BASE,
        "profile_dir": profile,
        "headless": True,
        "auth": {"credentials_file": str(DESKTOP / cfg_file)},
        "humanize": {"enabled": False},
    }
    g = Game(cfg, profile)
    g.start()
    g.goto(f"{BASE}/login")
    g.p.fill("input[name='login']", user, timeout=8000)
    g.p.fill("input[name='password']", password, timeout=8000)
    g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
    g.p.wait_for_load_state("domcontentloaded", timeout=20000)
    assert g.is_authenticated()
    return g


def send_bag_item(g: Game, recipient: str, item_id: str, message: str) -> bool:
    g.goto(f"{BASE}/user/mail/send/id/{recipient}")
    g.click_href("sendMessageForm:mailItemLink")
    g._settle()
    html = g.p.content()
    idx = None
    for chunk in html.split("<div"):
        if f"item/id/{item_id}" in chunk:
            m = re.search(r"sendItemContainer:items:(\d+):selectLink", chunk)
            if m:
                idx = m.group(1)
            break
    if idx is None:
        print("   !! вещь не найдена в списке отправки")
        return False
    print(f"   выбираю items:{idx}")
    g.click_href(f"sendItemContainer:items:{idx}:selectLink")
    g._settle()
    try:
        g.p.fill("textarea[name='text']", message, timeout=5000)
    except Exception:
        pass
    g.p.click("input[type='submit'][value='отправить'], input[name=':submit'][value='отправить']", timeout=8000)
    g._settle()
    print("   после отправки:", " ".join(g.body_text().split())[:220])
    return True


def main() -> int:
    g = make("barbars-firewhite-credentials.txt", "profile-probe-buy")
    try:
        print("1) МАГАЗИН: что лучше текущего набора")
        seen = {}
        for s in SETS:
            for it in g.shop_gear(s):
                seen[it.get("item_id")] = dict(it, set=s or "base")
        for it in seen.values():
            bonus = it.get("bonus", 0)
            if bonus:
                print(f"   +{bonus:<5} {it.get('name',''):<28} ур={it.get('level','?')} "
                      f"зол={it.get('gold',0)} сер={it.get('silver',0)} tier={it.get('tier','?')} id={it.get('item_id')}")
        print("   всего позиций:", len(seen))

        print("2) РАЗБОР дублей (не мифические)")
        for iid in BREAK_ITEMS:
            ok = g._crack_item_page(iid)
            g._settle()
            print(f"   {iid}: разобрано={ok} |", " ".join(g.body_text().split())[:160])

        print("3) ПЕРЧАТКИ-дубль -> keis")
        send_bag_item(g, KEIS_ID, GLOVES_DUP, "Перчатки Атланта 25 уровень (дубль)")

        print("4) ЗОЛОТО -> keis")
        ok = g.send_money_to(KEIS_ID, gold=43, silver=63)
        print("   отправлено:", ok, "|", " ".join(g.body_text().split())[:220])

        print("5) ИТОГ")
        g.goto(f"{BASE}/user")
        html = g.p.content()
        gold = re.findall(r"money_gold\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        silver = re.findall(r"money_silver\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        print("   кошелёк: золото=", gold[:1], "серебро=", silver[:1])
        g.goto(f"{BASE}/user/rack")
        print("   рюкзак:", " ".join(g.body_text().split())[:220])
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
