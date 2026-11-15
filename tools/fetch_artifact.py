"""Скачивает артефакт прогона GitHub Actions и распаковывает в каталог.

Используется, чтобы достать cookies сессии регистрации из артефакта
steelblue-registration-<run>.

Запуск: python tools\\fetch_artifact.py <run_id> [artifact_name] [dest]
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "p35084070-prog/barbars-agent"


def gh(*args: str) -> bytes:
    proc = subprocess.run(
        ["gh", *args], capture_output=True, check=True, cwd=str(ROOT)
    )
    return proc.stdout


def main() -> int:
    run_id = sys.argv[1]
    name_filter = sys.argv[2] if len(sys.argv) > 2 else "steelblue-registration"
    dest = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "knowledge" / "discovered" / "reg_artifact"
    dest.mkdir(parents=True, exist_ok=True)

    data = json.loads(gh("api", f"repos/{REPO}/actions/runs/{run_id}/artifacts").decode("utf-8-sig"))
    arts = [a for a in data.get("artifacts", []) if name_filter in a["name"]]
    if not arts:
        print("артефакт не найден:", [a["name"] for a in data.get("artifacts", [])])
        return 1
    for art in arts:
        print("артефакт:", art["name"], art["size_in_bytes"], "байт")
        raw = gh("api", art["archive_download_url"])
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                target = dest / Path(name).name
                target.write_bytes(zf.read(name))
                print("  сохранено:", target.name, target.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
