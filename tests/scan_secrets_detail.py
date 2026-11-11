"""Уточнить, какая именно строка учётных данных попадает в репозиторий (без печати секрета)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDS = [
    Path(r"C:\Users\Богдан\Desktop\barbars-agentcredentials.txt"),
    Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt"),
]

for path in CREDS:
    if not path.exists():
        continue
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for idx, value in enumerate(lines):
        hits = []
        for target in (ROOT / "deploy").rglob("*"):
            if target.is_file() and value in target.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(target.relative_to(ROOT)))
        if hits:
            print(f"{path.name}: строка {idx + 1} (длина {len(value)}) встречается в: {hits[:4]}")
