"""Этап 3: firewhite — надеть Наручи Голиафа (+14) и купить Молот Ветерана (+14, 80 сер);
keis — выставить дубли (Берсерк-набор + Перчатки) на аукцион."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
NAME_RE = re.compile(r"item/id/(\d+)\"><span>([^<]{2,60})</span>", re.S)


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


def wear_by_name(g: Game, name_part: str) -> bool:
    g.goto(f"{BASE}/user/rack")
    html = g.p.content()
    for chunk, index in g._item_blocks(html):
        m = NAME_RE.search(chunk)
        name = m.group(2) if m else ""
        if name_part in name and f"items:{index}:wearLink" in chunk:
            print(f"   надеваю [{index}] {name}")
            g.click_href(f"items:{index}:wearLink")
            g._settle()
            g.confirm_if_needed()
            g._settle()
            return True
    print(f"   НЕ НАЙДЕНО: {name_part}")
    return False


def buy_item(g: Game, shop_item_id: str, max_gold: int = 3) -> bool:
    """Купить товар магазина, если цена <= max_gold золота (серебро — 1 зол = 100 сер)."""
    g.goto(f"{BASE}/trade/auction/shop/item/id/{shop_item_id}")
    h = g.p.content()
    text = " ".join(g.body_text().split())
    m = re.search(r"Купить за\s*([0-9\s]+)(?:\s*зол)?(?:\s*([0-9\s]+)\s*сер)?", text)
    price_txt = m.group(0) if m else "?"
    gold = int(re.search(r"(\d+)\s*зол", price_txt).group(1)) if m and re.search(r"(\d+)\s*зол", price_txt) else 0
    silver = 0
    if m:
        nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
        silver = nums[-1] if nums else 0
        if re.search(r"(\d+)\s*сер", price_txt):
            silver = int(re.search(r"(\d+)\s*сер", price_txt).group(1))
    print(f"   цена: '{price_txt}' -> зол={gold} сер={silver} (серебро={silver} = {gold + silver/100:.2f} зол)")
    if gold > max_gold:
        print("   ОТКАЗ: больше лимита золота")
        return False
    if not g.click_href("border:buyoutLink"):
        print("   не нажалась кнопка покупки")
        return False
    g._settle()
    g.confirm_if_needed()
    g._settle()
    print("   после покупки:", " ".join(g.body_text().split())[:200])
    return True


def auction_item(g: Game, item_id: str, bid_gold: int, bid_silver: int,
                 buyout_gold: int, buyout_silver: int) -> bool:
    g.goto(f"{BASE}/item/id/{item_id}")
    h = g.p.content()
    m = re.search(r'href="([^"]*actionBlock:auctionLink[^"]*)"', h)
    if not m:
        print(f"   {item_id}: auctionLink НЕТ (нельзя на аукцион)")
        return False
    g.goto("https://barbars.ru/" + m.group(1).replace("../../", ""))
    g._settle()
    try:
        g.p.fill("input[name='bidGold']", str(bid_gold), timeout=5000)
        g.p.fill("input[name='bidSilver']", str(bid_silver), timeout=5000)
        g.p.fill("input[name='buyoutGold']", str(buyout_gold), timeout=5000)
        g.p.fill("input[name='buyoutSilver']", str(buyout_silver), timeout=5000)
    except Exception as e:
        print("   поля не заполнились:", e)
        return False
    g.p.click("input[type='submit'][value='выставить']", timeout=8000)
    g._settle()
    txt = " ".join(g.body_text().split())
    ok = "выставлена на аукцион" in txt.lower()
    print(f"   {item_id}: выставлено={ok}")
    return ok


def main() -> int:
    print("########## FIREWHITE ##########")
    g = make("barbars-firewhite-credentials.txt", "profile-probe-buy")
    try:
        print("1) Надеть Наручи Голиафа 25 (+14) из рюкзака")
        wear_by_name(g, "Наручи Голиафа")
        g.goto(f"{BASE}/user/body")
        print("   НАДЕТО:", " ".join(g.body_text().split())[:700])

        print("2) Купить Молот Ветерана 25 (+14)")
        if buy_item(g, "40099862"):
            g.take_mail()
            g._settle()
            wear_by_name(g, "Молот Ветерана")
        g.goto(f"{BASE}/user/body")
        print("   НАДЕТО:", " ".join(g.body_text().split())[:700])
        g.goto(f"{BASE}/user")
        html = g.p.content()
        gold = re.findall(r"money_gold\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        silver = re.findall(r"money_silver\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        print("   кошелёк: золото=", gold[:1], "серебро=", silver[:1])
    finally:
        g.close()

    print("\n########## KEIS: аукционы дубликатов ##########")
    g2 = make("barbars-agentcredentials.txt", "profile-probe-keis")
    try:
        g2.goto(f"{BASE}/user/rack")
        html = g2.p.content()
        dups = []
        for chunk, index in g2._item_blocks(html):
            m = NAME_RE.search(chunk)
            if not m:
                continue
            name, iid = m.group(2).strip(), m.group(1)
            if "Берсерка" in name or "Атланта" in name:
                dups.append((name, iid))
        print("   кандидаты на аукцион:", dups)
        for name, iid in dups:
            auction_item(g2, iid, bid_gold=1, bid_silver=0, buyout_gold=2, buyout_silver=0)
        g2.goto(f"{BASE}/user")
        html2 = g2.p.content()
        gold = re.findall(r"money_gold\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html2)
        silver = re.findall(r"money_silver\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html2)
        print("   кошелёк keis: золото=", gold[:1], "серебро=", silver[:1])
        g2.goto(f"{BASE}/user/rack")
        print("   рюкзак:", " ".join(g2.body_text().split())[:400])
    finally:
        g2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
