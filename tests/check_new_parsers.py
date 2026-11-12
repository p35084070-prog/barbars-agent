"""Проверка новых парсеров на сохранённом HTML."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars import pages  # noqa: E402

RAW = Path(__file__).resolve().parent / "raw"

bg = (RAW / "bg.html").read_text(encoding="utf-8")
bg_txt = (RAW / "bg.txt").read_text(encoding="utf-8")
info = pages.parse_battlefields(bg, bg_txt)
print("ПОЛЯ СРАЖЕНИЙ:", {k: v for k, v in info.items() if k != "text"})
print("  текст:", info["text"][:160])

ab = (RAW / "ability_buy_bg.html").read_text(encoding="utf-8")
data = pages.parse_ability_options(ab)
print("\nОЧКИ ПОЛЕЙ:", data["points"])
for opt in data["options"]:
    print("   ", opt)

print("\nНОРМАЛИЗАЦИЯ:", pages.cyr_normalize("Бepcepк"), "|", pages.cyr_normalize("Увoрот"))
print("КЛАССИФИКАЦИЯ:", pages.classify_target("Владения Медузы осталось 2 боя", "game/bg"))
