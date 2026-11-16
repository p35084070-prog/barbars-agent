"""Этап 4: keis забирает почту (деньги + перчатки), выставляет перчатки, ищем страницу лотов."""
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


def auction_item(g: Game, item_id: str, bid_gold: int, bid_silver: int,
                 buyout_gold: int, buyout_silver: int) -> bool:
    g.goto(f"{BASE}/item/id/{item_id}")
    h = g.p.content()
    m = re.search(r'href="([^"]*actionBlock:auctionLink[^"]*)"', h)
    if not m:
        print(f"   {item_id}: auctionLink НЕТ")
        print("      действия:", [" ".join(re.sub("<[^>]+>", "", x.group(2)).split())
                                  for x in re.finditer(r'<a[^>]+href="([^"]*actionBlock[^"]*)"[^>]*>(.*?)</a>', h, re.S)])
        return False
    g.goto("https://barbars.ru/" + m.group(1).replace("../../", ""))
    g._settle()
    try:
        g.p.fill("input[name='bidGold']", str(bid_gold), timeout=5000)
        g.p.fill("input[name='bidSilver']", str(bid_silver), timeout=5000)
        g.p.fill("input[name='buyoutGold']", str(buyout_gold), timeout=5000)
        g.p.fill("input[name='buyoutSilver']", str(buyout_silver), timeout=5000)
    except Exception as e:
        print("   поля:", e)
        return False
    g.p.click("input[type='submit'][value='выставить']", timeout=8000)
    g._settle()
    txt = " ".join(g.body_text().split()).lower()
    print(f"   {item_id}: выставлено={'выставлена на аукцион' in txt}")
    return "выставлена на аукцион" in txt


def main() -> int:
    g = make("barbars-agentcredentials.txt", "profile-probe-keis")
    try:
        print("1) ПОЧТА до забора:", " ".join(g.body_text().split())[:60] if False else "")
        g.goto(f"{BASE}/user/mail")
        print("   входящие:", " ".join(g.body_text().split())[:700])
        g.take_mail()
        g._settle()
        g.goto(f"{BASE}/user/mail")
        print("   после забора:", " ".join(g.body_text().split())[:400])

        print("2) КОШЕЛЁК после почты")
        g.goto(f"{BASE}/user")
        html = g.p.content()
        gold = re.findall(r"money_gold\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        silver = re.findall(r"money_silver\.png\"[^>]*>\s*<span[^>]*>\s*([^<]+)", html)
        print("   золото=", gold[:2], "серебро=", silver[:2])

        print("3) РЮКЗАК")
        g.goto(f"{BASE}/user/rack")
        html = g.p.content()
        gloves = None
        for chunk, index in g._item_blocks(html):
            m = NAME_RE.search(chunk)
            if not m:
                continue
            name, iid = m.group(2).strip(), m.group(1)
            print(f"   [{index}] {name}")
            if "Перчатки" in name:
                gloves = iid
        if gloves:
            print("4) Перчатки на аукцион:", gloves)
            auction_item(g, gloves, bid_gold=1, bid_silver=0, buyout_gold=2, buyout_silver=0)
        else:
            print("4) Перчатки не найдены в рюкзаке!")

        print("5) страница лотов: ищем ссылку")
        for url in (f"{BASE}/trade", f"{BASE}/trade/auctions", f"{BASE}/user/auction", f"{BASE}/trade/auction"):
            g.goto(url)
            t = " ".join(g.body_text().split())
            print(f"   {url}: {t[:180]}")
            for l in sorted(set(re.findall(r'href="([^"]*(?:uction|ot|lot)[^"]*)"', g.p.content())))[:12]:
                print("       ", l)
    finally:
        g.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
