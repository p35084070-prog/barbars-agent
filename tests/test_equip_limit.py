"""Тесты лимита надевания: `max_equip: 0` не должен означать «ничего не надеть»."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402


def test_zero_limit_means_unlimited():
    assert Game._equip_limit(0) == 20
    assert Game._equip_limit(-5) == 20


def test_explicit_limit_is_kept():
    assert Game._equip_limit(8) == 8
    assert Game._equip_limit(12) == 12


def test_steelblue_config_has_working_limit():
    import json

    cfg = json.loads((ROOT / "deploy/config-actions-steelblue.json").read_text(encoding="utf-8"))
    gear = cfg["gear"]
    assert gear["auto_equip"] is True
    assert Game._equip_limit(int(gear["max_equip"])) > 0
