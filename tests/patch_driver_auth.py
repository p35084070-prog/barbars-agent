"""Патч driver.py: поиск файла учётных данных + быстрый отказ в headless, если вход не удался."""
from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "driver.py"
text = path.read_text(encoding="utf-8")

old_creds = '''        if user and password:
            return user, password
        return None
'''

new_creds = '''        if user and password:
            return user, password
        return None

    def _credentials_file(self, raw: str) -> Path:
        """Где искать файл учётных данных.

        Путь в конфиге может быть относительным: сначала пробуем относительно
        каталога конфига, затем относительно корня репозитория (в облаке
        конфиги лежат в deploy/, а файл — в корне).
        """
        path = Path(raw)
        if path.is_absolute():
            return path
        candidates = []
        root = self.config.get("_root")
        if root:
            candidates.append(Path(root) / path)
        repo_root = Path(__file__).resolve().parents[1]
        candidates.append(repo_root / path)
        candidates.append(Path.cwd() / path)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
'''

assert old_creds in text, "не найден блок _load_credentials"
text = text.replace(old_creds, new_creds, 1)

old_loader = '''            raw_file = auth.get("credentials_file", "credentials.txt")
            path = Path(raw_file)
            if not path.is_absolute() and config.get("_root"):
                path = Path(config["_root"]) / raw_file
            if path.exists():'''

new_loader = '''            raw_file = auth.get("credentials_file", "credentials.txt")
            path = self._credentials_file(raw_file)
            if path.exists():'''

assert old_loader in text, "не найден загрузчик файла учётных данных"
text = text.replace(old_loader, new_loader, 1)

# headless-режим: не ждать ручного входа, а сразу завершиться
old_start = '''    def start(self, headless: bool | None = None) -> None:
        if self.page is not None:
            return
        headless = self.config.get("headless", False) if headless is None else headless'''

new_start = '''    def start(self, headless: bool | None = None) -> None:
        if self.page is not None:
            return
        headless = self.config.get("headless", False) if headless is None else headless
        self.headless = bool(headless)'''

assert old_start in text, "не найден start()"
text = text.replace(old_start, new_start, 1)

old_init = '''        self.human = Humanizer(config.get("humanize"))
        self.credentials = self._load_credentials(config)'''

new_init = '''        self.human = Humanizer(config.get("humanize"))
        self.headless = bool(config.get("headless", False))
        self.credentials = self._load_credentials(config)'''

assert old_init in text, "не найден __init__"
text = text.replace(old_init, new_init, 1)

old_login = '''        if self.auto_login():
            return True
        print("[вход] Сессия не активна: войди в игру в открытом окне браузера.")
        return self.wait_for_login(timeout_sec=timeout_sec)'''

new_login = '''        if self.auto_login():
            return True
        if self.headless:
            # в облаке/без окна ждать ручной вход бессмысленно — выходим сразу
            print("[вход] автовход не удался, а браузер без окна — продолжать нечем")
            return False
        print("[вход] Сессия не активна: войди в игру в открытом окне браузера.")
        return self.wait_for_login(timeout_sec=timeout_sec)'''

assert old_login in text, "не найден ensure_login"
text = text.replace(old_login, new_login, 1)

path.write_text(text, encoding="utf-8")
print("патч применён")
