"""Проверка: нет ли в репозитории ПАРОЛЕЙ (вторая строка файла учётных данных)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDS = [
    Path(r"C:\Users\Богдан\Desktop\barbars-agentcredentials.txt"),
    Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt"),
]

passwords: list[str] = []
for path in CREDS:
    if not path.exists():
        continue
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(lines) >= 2:
        passwords.append(lines[1])

skip_dirs = {".git", "profile", "logs", "__pycache__", "knowledge", "state", ".venv"}
problems: list[str] = []
checked = 0
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in skip_dirs for part in path.parts):
        continue
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".zip", ".pyc"}:
        continue
    checked += 1
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for secret in passwords:
        if secret in text:
            problems.append(str(path.relative_to(ROOT)))

if problems:
    print("НАЙДЕНЫ ПАРОЛИ:", problems)
    raise SystemExit(1)
print(f"паролей в репозитории нет (проверено файлов: {checked})")
