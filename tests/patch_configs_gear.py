"""Включить работу с рюкзаком в конфигах и пересобрать облачные конфиги."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GEAR = {
    "enabled": True,
    "keep_bag": 4,
    "max_equip": 8,
    "overflow_crack": "autoCrackUncommonLink",
}


def patch(name: str, autocrack_kind: str | None = None) -> None:
    path = ROOT / name
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["gear"] = dict(GEAR)
    if autocrack_kind:
        cfg.setdefault("autocrack", {})["kind"] = autocrack_kind
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("обновлён:", name)


patch("config-firewhite.json", "autoCrackUncommonLink")
patch("config.json")
