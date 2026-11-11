"""Извлечение сессии ok.ru из профиля встроенного браузера MiniMax Agent.

Профиль: %APPDATA%\\MiniMax Agent\\Partitions\\mavis-browser
Cookies (SQLite) расшифровываются через DPAPI + AES-128-CBC (как в Chromium).
Результат печатается в файл ok_session.json (host -> {name: value}).
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

APP_DIR = Path(os.environ["APPDATA"]) / "MiniMax Agent"
PARTITION = APP_DIR / "Partitions" / "mavis-browser"
OUT = Path(__file__).resolve().parents[1] / "ok_session.json"


def decrypt_value(blob: bytes, key: bytes | None) -> str:
    if not blob:
        return ""
    if blob[:3] in (b"v10", b"v11"):
        if key is None:
            return ""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        iv = blob[3:19]
        data = blob[19:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        dec = cipher.decryptor()
        out = dec.update(data) + dec.finalize()
        out = out[:-16]  # PKCS7
        return out.decode("utf-8", "replace")
    # v10 on windows always; other -> plain
    try:
        return blob.decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def get_key() -> bytes | None:
    state_path = APP_DIR / "Local State"
    if not state_path.exists():
        state_path = PARTITION / "Local State"
    if not state_path.exists():
        return None
    data = json.loads(state_path.read_text(encoding="utf-8"))
    enc = data.get("os_crypt", {}).get("encrypted_key")
    if not enc:
        return None
    raw = base64.b64decode(enc)
    if raw[:5] == b"DPAPI":
        raw = raw[5:]
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _unprotect(data: DATA_BLOB) -> bytes:
        out = DATA_BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(data), None, None, None, None, 0, ctypes.byref(out)
        ):
            raise OSError(ctypes.get_last_error())
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    decrypted = _unprotect(_blob(raw))
    return decrypted[5:]  # strip 'DPAPI' prefix


def open_db(src: Path, tmp: Path) -> sqlite3.Connection:
    """Открывает Cookies SQLite: сначала копия, иначе — только-чтение напрямую."""
    try:
        shutil.copy(src, tmp)
        return sqlite3.connect(tmp)
    except PermissionError:
        pass
    for uri in (f"file:{src.as_posix()}?mode=ro", f"file:{src.as_posix()}?immutable=1"):
        try:
            return sqlite3.connect(uri, uri=True)
        except sqlite3.Error:
            continue
    raise RuntimeError(f"не удалось открыть {src}")


def main() -> None:
    src = PARTITION / "Network" / "Cookies"
    if not src.exists():
        src = APP_DIR / "Network" / "Cookies"
    tmp = Path(tempfile.gettempdir()) / "mavis_browser_cookies.sqlite"
    con = open_db(src, tmp)
    rows = con.execute(
        "select host_key, name, path, expires_utc, is_secure, is_httponly, encrypted_value, value "
        "from cookies where host_key like '%ok.ru%' or host_key like '%odnoklassniki%'"
    ).fetchall()
    con.close()
    print(f"найдено куков ok.ru: {len(rows)}")
    try:
        key = get_key()
        print("ключ DPAPI:", "получен" if key else "нет")
    except Exception as exc:  # noqa: BLE001
        print("ошибка ключа:", exc)
        key = None

    session: dict[str, dict[str, str]] = {}
    for host, name, path, expires, secure, httponly, enc, plain in rows:
        value = decrypt_value(enc, key) if enc else plain
        if not value:
            continue
        session.setdefault(host, {})[name] = value
        print(f"  {host} :: {name} = {value[:24]}{'…' if len(value) > 24 else ''}")

    OUT.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"сохранено в {OUT}")


if __name__ == "__main__":
    main()
