"""Живая проверка: покупка вещи 25 ур в магазине снаряжения + вкладка «Вещи» в почте."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
FIREWHITE = "31389504"


def gold_silver(s) -> tuple[int, int]:
    h = s.get(f"{BASE}/user", timeout=30).text
    t = " ".join(text_of(h).split())
    m = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", t)
    return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    print("у keis золото/серебро до:", gold_silver(s))

    # покупаем «Перчатки Берсерка» (2 золота, +400)
    item_id = "40095139"
    page = s.get(f"{BASE}/trade/auction/shop/item/id/{item_id}", timeout=30)
    t = " ".join(text_of(page.text).split())
    print("товар:", t[:220])
    m = re.search(r'href="([^"]*border:buyoutLink[^"]*)"', page.text)
    if not m:
        print("ссылки покупки нет")
        return 1
    url = urljoin(f"{BASE}/trade/auction/shop/item/id/{item_id}", m.group(1).replace("&amp;", "&"))
    res = s.get(url, timeout=30, headers={"Referer": f"{BASE}/trade/auction/shop/item/id/{item_id}"})
    print("покупка -> HTTP", res.status_code, "|", " ".join(text_of(res.text).split())[:220])
    print("у keis золото/серебро после:", gold_silver(s))

    # что пришло: почта или рюкзак?
    mail = " ".join(text_of(s.get(f"{BASE}/user/mail", timeout=30).text).split())
    print("ПОЧТА:", mail[:300])
    rack = " ".join(text_of(s.get(f"{BASE}/user/rack", timeout=30).text).split())
    print("РЮКЗАК:", rack[:300])

    # вкладка «Вещи» в форме отправки (передача другому игроку)
    h = s.get(f"{BASE}/user/mail/send/id/{FIREWHITE}", timeout=30)
    m2 = re.search(r'href="([^"]*mailItemLink[^"]*)"', h.text)
    if m2:
        url2 = urljoin(f"{BASE}/user/mail/send/id/{FIREWHITE}", m2.group(1).replace("&amp;", "&"))
        h2 = s.get(url2, timeout=30, headers={"Referer": f"{BASE}/user/mail/send/id/{FIREWHITE}"})
        t2 = " ".join(text_of(h2.text).split())
        print("\nВКЛАДКА «ВЕЩИ»:", t2[:700])
        print("  ссылки:", [l for l in dict.fromkeys(re.findall(r'href="([^"]*wicket[^"]*)"', h2.text))][:14])
        print("  input:", re.findall(r"<input[^>]*name=[\"']([^\"']+)[\"']", h2.text)[:10])
    return 0


if __name__ == "__main__":
    sys.exit(main())
