"""Валюта прокачки: кузнец (подтверждение) и заточник (проценты)."""
from __future__ import annotations

import re
import sys
from urllib.parse import urljoin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])

    url = "https://barbars.ru/trade/smith/id/1950177878"
    page = s.get(url, timeout=30)
    mm = re.search(r'href="([^"]*spareItemsBlock:spareItems:0:selectLink[^"]*)"', page.text)
    u2 = urljoin(url, mm.group(1).replace("&amp;", "&"))
    p2 = s.get(u2, timeout=30)
    i = p2.text.find("Стоимость")
    print("=== кузнец: стоимость ===")
    print(" ", " ".join(p2.text[max(0, i - 300):i + 400].split())[:600])
    print("  иконки:", sorted(set(re.findall(r"icons/(money_\w+|ironbar|mifrilbar|silverbar)\.png", p2.text))))

    print("\n=== заточник: страница вещи ===")
    g = s.get("https://barbars.ru/trade/grinder/id/1950177878", timeout=30)
    gt = " ".join(text_of(g.text).split())
    print(" ", gt[:800])
    print("  иконки:", sorted(set(re.findall(r"icons/(money_\w+|ironbar|mifrilbar|silverbar)\.png", g.text))))
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", g.text, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        if t and t not in ("Выход", "Мой герой", "Мой клан", "На главную", "Лавка мастеров", "Форум", "Чат", "Лучшие", "Об игре", "Онлайн", "Служба поддержки", "Политика", "Другие игры", "Контакты", "Акция: скидка на Заточника"):
            print(f"   {t!r} -> {m.group(1).split('wicket:interface')[-1][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
