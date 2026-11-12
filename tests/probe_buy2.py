"""Разведка: покупка вещи со страницы вещи (витрина) + где почта."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    # 1. страница вещи с витрины: есть ли «купить»
    v = s.get(f"{BASE}/guild/public/store", timeout=30).text
    ids = list(dict.fromkeys(re.findall(r"item/id/(\d+)", v)))[:3]
    for item_id in ids:
        page = s.get(f"{BASE}/item/id/{item_id}", timeout=30).text
        t = " ".join(text_of(page).split())
        print(f"\n--- вещь {item_id}: {t[:220]}")
        links = list(dict.fromkeys(re.findall(r'href="([^"]+)"', page)))
        print("   ссылки:", [l for l in links if not l.endswith(".css")][:12])
        print("   есть buy:", "buy" in page.lower(), "| price:", "price" in page.lower())

    # 2. почта: пробуем типовые адреса
    for path in ("/user/mail", "/user/mails", "/user/messages", "/user/post", "/user/news",
                 "/user/mailbox", "/messages", "/user/letters"):
        h = s.get(BASE + path, timeout=30)
        t = " ".join(text_of(h.text).split())
        if "Вход для игроков" in t:
            continue
        print(f"\n=== {path} -> {h.url}")
        print("   ", t[:260])

    # 3. где встречается «новая почта» на главной
    home = s.get(f"{BASE}/", timeout=30)
    print("\nпочта на главной:", "новая почта" in home.text.lower())
    for m in list(re.finditer(r"[^<>]{0,40}почт[^<>]{0,40}", home.text, re.I))[:6]:
        print("   ", m.group(0).strip()[:100])
    return 0


if __name__ == "__main__":
    sys.exit(main())
