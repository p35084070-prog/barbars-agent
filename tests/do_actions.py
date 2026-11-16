"""Боевые действия: keis отдаёт амулет firewhite + выставляет дубль на аукцион.

Затем firewhite забирает почту, надевает амулет 25 ур. и разбирает дубли.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
AMULET_TO_FIREWHITE = "2093127636"   # 1-й Амулет Берсерка 25 -> firewhite
AMULET_DUP = "2093103442"             # 2-й Амулет Берсерка 25 -> аукцион
FIREWHITE_ID = "31389504"


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
    """Передать одну вещь из рюкзака через почту (вкладка «Вещи» -> Рюкзак -> выбрать)."""
    g.goto(f"{BASE}/user/mail/send/id/{recipient}")
    g.click_href("sendMessageForm:mailItemLink")
    g._settle()
    html = g.p.content()
    # находим индекс селекта по item id в блоке
    idx = None
    for chunk in html.split("<div"):
        if f"item/id/{item_id}" in chunk:
            m = re.search(r"sendItemContainer:items:(\d+):selectLink", chunk)
            if m:
                idx = m.group(1)
            break
    if idx is None:
        # запасной путь: по порядку в рюкзаке
        print("   (селект по id не найден, пробую список)")
        return False
    print(f"   выбираю items:{idx}")
    g.click_href(f"sendItemContainer:items:{idx}:selectLink")
    g._settle()
    try:
        g.p.fill("textarea[name='text']", message, timeout=5000)
    except Exception:
        pass
    g.p.click("input[name=':submit'][value='отправить'], input[type='submit'][value='отправить']", timeout=8000)
    g._settle()
    return True


def put_on_auction(g: Game, item_id: str, bid_gold: int, bid_silver: int,
                   buyout_gold: int, buyout_silver: int) -> bool:
    g.goto(f"{BASE}/item/id/{item_id}")
    h = g.p.content()
    m = re.search(r'href="([^"]*actionBlock:auctionLink[^"]*)"', h)
    if not m:
        print("   auctionLink не найден")
        return False
    g.goto("https://barbars.ru/" + m.group(1).replace("../../", ""))
    g._settle()
    try:
        g.p.fill("input[name='bidGold']", str(bid_gold), timeout=5000)
        g.p.fill("input[name='bidSilver']", str(bid_silver), timeout=5000)
        g.p.fill("input[name='buyoutGold']", str(buyout_gold), timeout=5000)
        g.p.fill("input[name='buyoutSilver']", str(buyout_silver), timeout=5000)
    except Exception as e:
        print("   заполнение не удалось:", e)
        return False
    g.p.click("input[type='submit'][value='выставить']", timeout=8000)
    g._settle()
    print("   после выставления:", " ".join(g.body_text().split())[:400])
    return True


def main() -> int:
    print("########## KEIS ##########")
    g = make("barbars-agentcredentials.txt", "profile-probe-keis")
    try:
        print("1) передаю Амулет Берсерка 25 -> fire white ii")
        ok = send_bag_item(g, FIREWHITE_ID, AMULET_TO_FIREWHITE, "Амулет Берсерка 25 уровень")
        print("   отправлено:", ok, "|", " ".join(g.body_text().split())[:300])
        print("2) выставляю 2-й Амулет на аукцион")
        put_on_auction(g, AMULET_DUP, bid_gold=1, bid_silver=50, buyout_gold=3, buyout_silver=0)
        g.goto(f"{BASE}/user/rack")
        html = g.p.content()
        for chunk, index in g._item_blocks(html):
            m = re.search(r"item/id/(\d+)\"><span>([^<]{2,60})</span>", chunk, re.S)
            if m:
                print(f"   рюкзак [{index}] {m.group(2)}")
    finally:
        g.close()

    print("\n########## FIREWHITE ##########")
    g2 = make("barbars-firewhite-credentials.txt", "profile-probe-buy")
    try:
        print("3) забираю почту")
        g2.take_mail()
        g2._settle()
        g2.goto(f"{BASE}/user/rack")
        html = g2.p.content()
        for chunk, index in g2._item_blocks(html):
            m = re.search(r"item/id/(\d+)\"><span>([^<]{2,60})</span>", chunk, re.S)
            flags = []
            if "bonusdarkiron" in chunk:
                flags.append("МИФИЧ")
            if f"items:{index}:wearLink" in chunk:
                flags.append("wear")
            if f"items:{index}:crackLink" in chunk:
                flags.append("crack")
            if m:
                print(f"   рюкзак [{index}] {m.group(2):<36} {' '.join(flags)}")
        print("4) надеваю Амулет Берсерка 25")
        g2.goto(f"{BASE}/user/rack")
        for chunk, index in g2._item_blocks(html):
            m = re.search(r"item/id/(\d+)\"><span>([^<]{2,60})</span>", chunk, re.S)
            if m and "Амулет Берсерка" in m.group(2) and f"items:{index}:wearLink" in chunk:
                print("   надеваю", m.group(2))
                g2.click_href(f"items:{index}:wearLink")
                g2._settle()
                g2.confirm_if_needed()
                g2._settle()
                break
        g2.goto(f"{BASE}/user/body")
        print("   НАДЕТО:", " ".join(g2.body_text().split())[:900])
    finally:
        g2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
