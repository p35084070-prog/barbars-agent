"""Почистить сундук героя от хлама (разобрать на железо или выбросить).

Использует ту же логику, что и агент в цикле (`Game.clean_chest`):
- мифические/легендарные/эпические (награда за дракона) не трогаем;
- «Лучше» — такую вещь надо надеть, а не выбрасывать;
- обычный хлам: `--mode crack` — сначала разобрать на железо, иначе выкинуть;
  `--mode drop` — только выбросить.

Запуск:
    python tools\\clean_chest.py --config deploy\\config-actions-steelblue.json \
        --creds credentials\\steelblue.txt [--mode crack|drop] [--limit 20]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402
from run import load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--mode", default="crack", choices=["crack", "drop"])
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    config = load_config(ROOT / args.config)
    creds = Path(args.creds)
    if not creds.is_absolute():
        creds = ROOT / creds

    with tempfile.TemporaryDirectory(prefix="cleanchest-", ignore_cleanup_errors=True) as tmp:
        game = Game(config, Path(tmp))
        game.start(headless=True)
        if not game.ensure_login(timeout_sec=120):
            print("CLEAN_CHEST " + json.dumps({"error": "вход не подтверждён"}, ensure_ascii=False))
            return 1
        before = game.bag_counts()
        res = game.clean_chest(limit=args.limit, action=args.mode)
        after = game.bag_counts()

    print(
        "CLEAN_CHEST "
        + json.dumps(
            {
                "mode": args.mode,
                "cracked": res.get("cracked", 0),
                "dropped": res.get("dropped", 0),
                "skipped": res.get("skipped", 0),
                "chest_before": f"{before.get('chest_used')}/{before.get('chest_total')}",
                "chest_after": f"{after.get('chest_used')}/{after.get('chest_total')}",
                "bag_after": f"{after.get('bag_used')}/{after.get('bag_total')}",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
