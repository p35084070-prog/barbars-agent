"""Докупить конкретную вещь, когда она появится в «Магазине снаряжения».

Нужно, чтобы вернуть вещь, случайно разобранную (Бурка Ветерана 25 ур.),
или чтобы закрыть пробел в комплекте 25 уровня.

Покупка идёт только если цена укладывается в лимит игрока: **не больше
1 золота на вещь** (серебро считается как 1 зол = 100 сер, как в
`Game.buy_shop_item_capped`). Если вещь уже есть в сундуке/рюкзаке — не
покупаем.

Запуск:
    python tools\\buy_missing_gear.py --config deploy\\config-actions-steelblue.json \
        --creds credentials\\steelblue.txt --want "Бурка Ветерана" --level 25
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

SETS = ["", "goliaf", "atlant", "veteran"]


def own_item_names(game: Game) -> str:
    """Названия вещей в сундуке и рюкзаке (одной строкой — для поиска)."""
    out = []
    for url in ("https://barbars.ru/user/store", "https://barbars.ru/user/rack"):
        game.goto(url)
        out.append(" ".join(game.body_text().split()))
    return " ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--want", required=True, help="название вещи (подстрока)")
    ap.add_argument("--level", type=int, default=25)
    ap.add_argument("--max-gold", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config = load_config(ROOT / args.config)
    creds = Path(args.creds)
    if not creds.is_absolute():
        creds = ROOT / creds

    out: dict[str, object] = {"want": args.want, "level": args.level}
    with tempfile.TemporaryDirectory(prefix="buymissing-", ignore_cleanup_errors=True) as tmp:
        game = Game(config, Path(tmp))
        game.start(headless=True)
        if not game.ensure_login(timeout_sec=120):
            out["error"] = "вход не подтверждён"
            print("BUY_MISSING " + json.dumps(out, ensure_ascii=False), flush=True)
            return 1

        owned = own_item_names(game)
        out["already_owned"] = args.want in owned
        offers: list[dict[str, object]] = []
        for set_name in SETS:
            try:
                items = game.shop_gear(set_name)
            except Exception as exc:  # noqa: BLE001
                out.setdefault("errors", []).append(f"набор {set_name}: {exc}")
                continue
            for it in items:
                if args.want.lower() not in str(it.get("name", "")).lower():
                    continue
                if args.level and int(it.get("level", 0)) != args.level:
                    continue
                offers.append(it)
        out["offers"] = [
            {
                "name": it.get("name"),
                "item_id": it.get("item_id"),
                "level": it.get("level"),
                "gold": it.get("gold"),
                "silver": it.get("silver"),
            }
            for it in offers
        ]

        if not offers:
            out["result"] = "товара нет в магазине — ждём ротацию"
        elif out["already_owned"]:
            out["result"] = "вещь уже есть — не покупаем"
        elif args.dry_run:
            out["result"] = "dry-run: покупка не выполнялась"
        else:
            best = min(offers, key=lambda i: int(i.get("gold", 0)) * 100 + int(i.get("silver", 0)))
            ok, msg = game.buy_shop_item_capped(str(best.get("item_id")), max_gold=args.max_gold)
            out["bought"] = {"name": best.get("name"), "ok": ok, "msg": msg}

    print("BUY_MISSING " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
