"""Сбросить дневные счётчики под начало нового игрового дня.

Игровой день в «Варварах» сбрасывается не в полночь по местному времени,
а в своё время (наблюдение: 11.11 около 13:00 МСК бесплатные бои
восстановились с 0 до 2 подземелий и 3 дуэлей). Чтобы агент не считал,
что «подарок/опыт/авторазбор уже взяты сегодня», счётчики обнуляем.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
today = datetime.now().strftime("%Y-%m-%d")

for account in ("keis", "firewhite"):
    path = ROOT / "state" / account / "daily.json"
    data = {
        "date": today,
        "sold": 0,
        "exp": 0,
        "gift": False,
        "autocrack": False,
        "award": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("сброшен:", path)
