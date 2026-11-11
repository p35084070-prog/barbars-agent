"""Проверка: есть ли в браузерах пользователя активная сессия ok.ru.

Источники:
  - Google Chrome (Default) -> Network/Cookies
  - Edge (Default)          -> Network/Cookies
  - профили Playwright агента
Печатает только имена хостов и кол-ва куков (значения не выводятся).
"""
import os
import shutil
import sqlite3
import sys
import tempfile

CANDIDATES = [
    (r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies", "chrome-default"),
    (r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies", "edge-default"),
    (r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Profile 1\Network\Cookies", "edge-profile1"),
    (r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\Default\Network\Cookies", "brave-default"),
]


def probe(path: str, label: str) -> None:
    path = os.path.expandvars(path)
    if not os.path.exists(path):
        print(f"[{label}] нет файла: {path}")
        return
    tmp = os.path.join(tempfile.gettempdir(), f"probe_{label}.sqlite")
    shutil.copy(path, tmp)
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "select host_key, name, length(encrypted_value) from cookies where host_key like '%ok.ru%'"
        ).fetchall()
        con.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] ошибка чтения: {exc}")
        return
    if not rows:
        print(f"[{label}] ok.ru: куков нет")
        return
    print(f"[{label}] ok.ru: {len(rows)} куков")
    for host, name, length in rows:
        print(f"    {host} :: {name} (enc={length})")


def main() -> None:
    for path, label in CANDIDATES:
        probe(path, label)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for folder in ("profile", "profile-ok", "profile-test"):
        candidate = os.path.join(root, folder, "Default", "Network", "Cookies")
        probe(candidate, f"pw-{folder}")
    sys.exit(0)


if __name__ == "__main__":
    main()
