"""Проверяем, есть ли живая сессия ОК в сохранённых профилях Chromium."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["profile-ok", "profile-ok-mobile", "profile-ok-phone"]


def cookie_db(profile: Path) -> Path | None:
    for rel in ("Default/Cookies", "Cookies", "Default/Network/Cookies"):
        cand = profile / rel
        if cand.exists():
            return cand
    return None


def main() -> None:
    for name in NAMES:
        prof = ROOT / name
        print(f"== {name}: {'есть' if prof.exists() else 'нет'}")
        db = cookie_db(prof) if prof.exists() else None
        if db is None:
            print("   куки не найдены")
            continue
        tmp = Path(tempfile.mkdtemp()) / "c.db"
        try:
            shutil.copy(db, tmp)
            con = sqlite3.connect(tmp)
            rows = con.execute(
                "select host_key, name, expires_utc from cookies "
                "where host_key like '%ok.ru%' order by host_key, name"
            ).fetchall()
            print(f"   всего ok.ru-кук: {len(rows)}")
            for host, cname, exp in rows:
                print(f"   {host:28} {cname:24} expires={exp}")
        except Exception as exc:  # noqa: BLE001
            print(f"   ОШИБКА чтения: {exc}")
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
