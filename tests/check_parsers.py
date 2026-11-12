"""Проверка парсеров на сохранённом HTML (без сети)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402

RAW = Path(__file__).resolve().parent / "raw"

market = (RAW / "market.html").read_text(encoding="utf-8")
body = (RAW / "keis_body.html").read_text(encoding="utf-8")
item = (RAW / "item_amulet.txt").read_text(encoding="utf-8")

lots = pages.parse_market_lots(market)
print("ЛОТОВ:", len(lots))
for lot in lots[:6]:
    print(f"  {lot['name']:<24} ур={lot['level']:<3} tier={lot['tier']:<12} "
          f"зол={lot['gold']} сер={lot['silver']} цена={lot['price_silver']}")

worn = pages.parse_worn_gear(body)
print("НАДЕТО (keis):", [(w["slot"], w["name"], w["level"]) for w in worn])

print("ЦЕНА амулета:", pages.parse_price_text(item))
print("ЦЕНА «Купить за 6 зол 50 сер»:", pages.parse_price_text("Купить за 6 зол 50 сер"))
print("ЦЕНА «Выкупить сразу за 23»:", pages.parse_price_text("Выкупить сразу за 23"))
print("СЛОТЫ:", [pages.slot_of(n) for n in
                 ("Шлем Ветерана", "Амулет Ветерана", "Бурка Ветерана", "Наручи Ветерана",
                  "Кираса Голиафа", "Топор Берсерка", "Сапоги Ветерана", "Поножи Голиафа")])
