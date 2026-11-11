"""Создать заготовки файлов дневных счётчиков в state/ (они коммитятся в репозиторий)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
today = datetime.now().strftime("%Y-%m-%d")

for account in ("keis", "firewhite"):
    folder = ROOT / "state" / account
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "daily.json"
    data = {
        "date": today,
        "sold": 0,
        "exp": 0,
        "gift": False,
        "autocrack": False,
        "award": False,
    }
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("готов:", path)
