"""Купить снаряжение в «Магазине снаряжения» и (опционально) отправить герою почтой.

Печатает кошелёк до/после (золото/серебро) — так видно, какой валютой
списалась оплата, и куда попала купленная вещь (рюкзак / витрина).

Запуск:
    python tools\\buy_gear.py --config deploy\\config-actions-keis.json \
        --item-id 40121857 [--max-gold 1] [--send-to 31390082] [--name "Сапоги"]
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


def wallet(game: Game) -> dict[str, int]:
    st = game.status()
    return {
        "gold": int(st.gold or 0),
        "silver": int(st.silver or 0),
        "iron": int(st.iron or 0),
        "mifril": int(st.mifril or 0),
        "bottles": int(st.bottles or 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--item-id", action="append", default=[])
    ap.add_argument("--max-gold", type=int, default=1)
    ap.add_argument("--send-to", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    config = load_config(ROOT / args.config)
    out: dict[str, object] = {"label": args.label or args.config}

    with tempfile.TemporaryDirectory(prefix="buy-gear-") as tmp:
        game = Game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=120):
                out["error"] = "вход не подтверждён"
                print("BUY_GEAR " + json.dumps(out, ensure_ascii=False), flush=True)
                return 1
            out["wallet_before"] = wallet(game)
            bought: list[dict[str, str]] = []
            for item_id in args.item_id:
                try:
                    price = game.shop_item_price(item_id)
                except Exception as exc:  # noqa: BLE001
                    out.setdefault("price_errors", []).append(f"{item_id}: {exc}")
                    continue
                gold_need, silver_need = price
                out.setdefault("prices", []).append(
                    {"item_id": item_id, "gold": gold_need, "silver": silver_need}
                )
                ok, msg = game.buy_shop_item_capped(item_id, max_gold=args.max_gold)
                out.setdefault("results", []).append(
                    {"item_id": item_id, "ok": bool(ok), "msg": msg}
                )
                if ok:
                    bought.append({"item_id": item_id})
            out["wallet_after"] = wallet(game)
            try:
                out["bag"] = [
                    {"id": i["item_id"], "name": i["name"]}
                    for i in game.bag_items()
                    if i["name"]
                ][:30]
            except Exception as exc:  # noqa: BLE001
                out["bag_error"] = str(exc).splitlines()[0][:200]
            if args.send_to:
                sent = []
                for item_id in args.item_id:
                    try:
                        ok = game.send_bag_item_to(args.send_to, item_id)
                    except Exception as exc:  # noqa: BLE001
                        ok = f"ошибка: {exc}"
                    sent.append({"item_id": item_id, "sent": ok})
                out["sent"] = sent
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("BUY_GEAR " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
