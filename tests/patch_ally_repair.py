"""Добавить блок ally_repair в локальные конфиги (keis/firewhite/vagojan)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BLOCKS = {
    "config.json": {
        "enabled": True,
        "heroes": ["1286381"],
        "check_interval_min": 60,
        "keep_iron": 20000,
    },
    "config-firewhite.json": {
        # железо у firewhite нужно ему самому на мастерство — ремонтирует keis
        "enabled": False,
        "heroes": ["1286381"],
        "check_interval_min": 60,
        "keep_iron": 20000,
    },
    "config-vagojan.json": {
        "enabled": True,
        "heroes": [],
        "check_interval_min": 60,
        "keep_iron": 20000,
    },
}

for name, block in BLOCKS.items():
    path = ROOT / name
    if not path.exists():
        print("нет файла:", name)
        continue
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["ally_repair"] = block
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("обновлён:", name)
