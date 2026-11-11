"""Загрузка учётных данных нового героя (файл лежит вне репозитория)."""
from __future__ import annotations

import json
import os
from pathlib import Path

CANDIDATES = [
    os.environ.get("BARBARS_CREDS_FIREWHITE", ""),
    r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.json",
    str(Path(__file__).resolve().parents[1] / "credentials-firewhite.json"),
]


def load() -> dict:
    for candidate in CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.exists():
            continue
        if path.suffix == ".txt":
            lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if len(lines) >= 2:
                return {"nick": lines[0], "password": lines[1]}
            continue
        return json.loads(path.read_text(encoding="utf-8"))
    raise SystemExit("файл учётных данных не найден")
