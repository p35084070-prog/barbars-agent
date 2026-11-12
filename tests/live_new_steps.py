"""Живая проверка новых шагов: дубли, рынок лотов, цена товара."""
from __future__ import annotations

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
    print("########## KEIS ##########")
    g = make("barbars-agentcredentials.txt", "profile-probe-keis")
    try:
        worn = g.worn_gear()
        print("НАДЕТО:", [(w["slot"], w["name"], w.get("level")) for w in worn])
        bag = g.bag_items()
        busy = {pages.slot_of(w["name"])[0]: w["name"] for w in worn}
        dups = []
        for item in bag:
            slot, _ = pages.slot_of(str(item.get("name", "")))
            mark = []
            if item.get("personal"):
                mark.append("личный")
            if item.get("mythic"):
                mark.append("мифич")
            if slot and slot in busy:
                mark.append("ДУБЛЬ")
                dups.append(item)
            print(f"  {item.get('name',''):<28} {' '.join(mark)}")
        print("ДУБЛЕЙ:", [d.get("name") for d in dups])
        print("снаряжение firewhite:", [(w["slot"], w["name"], w.get("level")) for w in g.other_hero_gear("31389504")])
        lots = g.market_lots()
        print(f"ЛОТОВ: {len(lots)}")
        for lot in lots[:12]:
            print(f"  {lot['name']:<26} ур={lot['level']:<3} tier={lot['tier']:<12} "
                  f"зол={lot['gold']} сер={lot['silver']} цена={lot['price_silver']} id={lot['item_id']}")
    finally:
        g.close()

    print("\n########## FIREWHITE ##########")
    g2 = make("barbars-firewhite-credentials.txt", "profile-probe-buy")
    try:
        items = []
        for s in ("", "goliaf", "atlant", "veteran"):
            items += g2.shop_gear(s)
        worn2 = g2.worn_gear()
        print("НАДЕТО:", [(w["slot"], w["name"], w.get("level")) for w in worn2])
        for it in items:
            if int(it.get("bonus", 0)) > 0:
                print(f"  +{it['bonus']:<4} {it['name']:<28} ур={it['level']:<3} "
                      f"зол={it['gold']} сер={it['silver']} ok={it.get('price_ok')} id={it['item_id']}")
        picked = pages.pick_shop_items(items, worn2, 3, 0, (), True, min_bonus=10,
                                       avoid_same_name=True, min_level=25)
        print("К ПОКУПКЕ (min_bonus=10):", [(p["name"], p["bonus"], p["gold"], p["silver"]) for p in picked])
        for it in items[:3]:
            price = g2.shop_item_price(str(it.get("item_id")))
            print(f"  цена на странице «{it.get('name')}»: зол={price[0]} сер={price[1]}")
    finally:
        g2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
