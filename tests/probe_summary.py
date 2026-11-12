"""Сводка: магазин снаряжения (остатки лотов), аукцион (свои лоты), почта."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402
from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    for label, fname in (("firewhite", "barbars-firewhite-credentials.txt"),
                         ("keis", "barbars-agentcredentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        print(f"\n======== {label} ========")

        # магазин снаряжения: что в наличии и в лимите 3 золота
        cheap = []
        for set_name in ("", "goliaf", "atlant", "veteran"):
            html = s.get(f"{BASE}/trade/auction/shop" + (f"/0/{set_name}" if set_name else ""), timeout=30).text
            for it in pages.parse_shop_gear(html):
                if it["gold"] <= 3:
                    cheap.append(it)
        print("  в лимите 3 золота:", [(i["name"], i["gold"], i["silver"], i["bonus"]) for i in cheap] or "нет")
        print("  всего лотов:", len(cheap))

        # аукцион: свои лоты (если доступен)
        h = s.get(f"{BASE}/trade/bazaar", timeout=30)
        if "Аукцион ресурсов" in text_of(h.text):
            s.get(f"{BASE}/trade/bazaar", timeout=30)
            html = s.get(f"{BASE}/trade/bazaar", timeout=30).text
            m = re.search(r'href="([^"]*filterMyLotsLink[^"]*)"', html)
            if m:
                from urllib.parse import urljoin
                url = urljoin(f"{BASE}/trade/bazaar", m.group(1).replace("&amp;", "&"))
                html2 = s.get(url, timeout=30).text
                t2 = " ".join(text_of(html2).split())
                i = t2.find("Мои лоты")
                print("  свои лоты:", t2[i:i + 300] if i >= 0 else t2[:200])
            else:
                print("  аукцион доступен, вкладка лотов не найдена")
        else:
            print("  аукцион недоступен")

        # почта
        mail = " ".join(text_of(s.get(f"{BASE}/user/mail", timeout=30).text).split())
        i = mail.find("Почта")
        print("  почта:", mail[i:i + 260] if i >= 0 else mail[:200])

        # что надето (уровень снаряжения)
        hero = s.get(f"{BASE}/user", timeout=30).text
        hid = re.search(r"user/body/id/(\d+)", hero)
        if hid:
            worn = pages.parse_worn_gear(s.get(f"{BASE}/user/body/id/{hid.group(1)}", timeout=30).text)
            print("  надето:", [(w["slot"], w["name"]) for w in worn])
    return 0


if __name__ == "__main__":
    sys.exit(main())
