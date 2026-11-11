"""Перенос файла с паролем из репозитория на рабочий стол + правка тестовых скриптов."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "credentials-firewhite.json"
DST = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.json")

if SRC.exists():
    if not DST.exists():
        shutil.copy2(SRC, DST)
    SRC.unlink()
    print("файл с паролем перемещён на рабочий стол:", DST)

helper = '''"""Загрузка учётных данных нового героя (файл лежит вне репозитория)."""
from __future__ import annotations

import json
import os
from pathlib import Path

CANDIDATES = [
    os.environ.get("BARBARS_CREDS_FIREWHITE", ""),
    r"C:\\Users\\Богдан\\Desktop\\barbars-firewhite-credentials.json",
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
'''

(ROOT / "tests" / "fw_auth.py").write_text(helper, encoding="utf-8")

pattern = re.compile(
    r'creds\s*=\s*json\.loads\(\(ROOT / "credentials-firewhite\.json"\)\.read_text\(encoding="utf-8"\)\)'
)
changed = []
for path in (ROOT / "tests").glob("fw_*.py"):
    text = path.read_text(encoding="utf-8")
    if "credentials-firewhite.json" not in text:
        continue
    new = pattern.sub("creds = fw_auth.load()", text)
    if new == text:
        # другой вариант записи — заменяем строку с json.loads целиком
        new = re.sub(
            r'creds = json\.loads\([^\n]*credentials-firewhite\.json[^\n]*\)',
            "creds = fw_auth.load()",
            text,
        )
    if new != text:
        if "import fw_auth" not in new:
            new = new.replace("import requests", "import requests\n\nimport fw_auth", 1)
        path.write_text(new, encoding="utf-8")
        changed.append(path.name)
print("обновлено:", ", ".join(changed) or "ничего")
