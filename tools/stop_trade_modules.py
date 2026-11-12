"""Остановить (не удалить) торговые модули во всех конфигах героев.

Выключаются: market (продажа мифрила/бутылок), shop (магазин снаряжения),
auction (аукцион вещей), trade_market (рынок аукционов — покупка вещей).
Остальные параметры блоков сохраняются как есть.

Запуск:
    python tools\stop_trade_modules.py [--включить]
"""
from __future__ import annotations

import json
import sys
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


def main() -> int:
    enable = "--включить" in sys.argv
    value = True if enable else False
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            print(f"{name}: файла нет")
            continue
        raw = path.read_text(encoding="utf-8")
        config = json.loads(raw)
        changed = []
        for module in MODULES:
            block = config.get(module)
            if not isinstance(block, dict):
                continue
            if block.get("enabled") != value:
                block["enabled"] = value
                changed.append(module)
        if not changed:
            print(f"{name}: уже {'включены' if value else 'выключены'} — без изменений")
            continue
        text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        print(f"{name}: {', '.join(changed)} -> enabled={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
