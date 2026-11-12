"""Статус торговых модулей (рынок, магазин, аукцион, рынок аукционов)
во всех конфигах героев.

Запуск:
    python tools\check_trade_modules.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = [
    "config.json",
    "config-firewhite.json",
    "config-ok.json",
    "deploy/config-actions-keis.json",
    "deploy/config-actions-firewhite.json",
    "deploy/config-cloud-keis.json",
    "deploy/config-cloud-firewhite.json",
]

MODULES = ["market", "shop", "auction", "trade_market"]


def main() -> None:
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            print(f"{name}: файла нет")
            continue
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"{name}: не читается ({exc})")
            continue
        parts = []
        for module in MODULES:
            block = config.get(module)
            if block is None:
                parts.append(f"{module}=нет блока")
            elif isinstance(block, dict):
                parts.append(f"{module}.enabled={block.get('enabled')}")
        print(f"{name}: account={config.get('account')} | " + " | ".join(parts))


if __name__ == "__main__":
    main()
