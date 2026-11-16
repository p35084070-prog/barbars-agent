"""Нормализация кредов героя и перезапись в GitHub Secrets.

Причина появления: секреты записывались через PowerShell-перенаправление, и
перед значением остался BOM (U+FEFF) — с ним вход в игру не проходит
(«Неверный ник или пароль»). Здесь значение очищается и перезаписывается.

Запуск (в облаке): python tools\\normalize_secret.py <аккаунт>
Креды берутся из Secrets через env LOGIN/PASSWORD, новые записываются через gh.
"""
from __future__ import annotations

import os
import subprocess
import sys


def clean(value: str) -> str:
    return value.replace("\ufeff", "").replace("\u200b", "").strip()


def main() -> int:
    account = sys.argv[1] if len(sys.argv) > 1 else "steelblue"
    login = clean(os.environ.get("LOGIN", ""))
    password = clean(os.environ.get("PASSWORD", ""))
    if not login or not password:
        print("LOGIN/PASSWORD пустые — нечего чинить")
        return 1
    print("ник очищен, длина:", len(login))
    print("пароль очищен, длина:", len(password))
    repo = os.environ.get("GITHUB_REPOSITORY", "p35084070-prog/barbars-agent")
    for name, value in (
        (f"BARBARS_{account.upper()}_LOGIN", login),
        (f"BARBARS_{account.upper()}_PASSWORD", password),
    ):
        subprocess.run(
            ["gh", "secret", "set", name, "-R", repo],
            input=value,
            text=True,
            check=True,
        )
        print(f"секрет {name} перезаписан")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
