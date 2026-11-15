"""Собрать купленные вещи и отправить их другому герою почтой.

Шаги:
  1. на главной странице нажимаем все ссылки «в рюкзак» — вещи из панели
     «новый предмет» переезжают в рюкзак;
  2. печатаем содержимое рюкзака и витрины;
  3. по --send-to отправляем нужные вещи почтой (по одной, по id предмета).

Запуск:
    python tools\\gear_transfer.py --config deploy\\config-actions-keis.json \
        --names "Сапоги Берсерка" "Шлем Берсерка" --send-to 31390082
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402
from run import load_config  # noqa: E402


def collect_new_items(game: Game, limit: int = 20) -> int:
    """Нажать «в рюкзак» у вещей из панели «новый предмет»."""
    moved = 0
    for _ in range(limit):
        game.goto("https://barbars.ru/user")
        html = game.p.content()
        target = None
        for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split()).lower()
            if label.startswith("в ") and "рюкзак" in label:
                target = m.group(1)
                break
        if target is None:
            break
        if not game.click_href(target):
            break
        game._settle()
        moved += 1
    return moved


def list_items(game: Game, url: str) -> list[dict[str, str]]:
    game.goto(url)
    html = game.p.content()
    out = []
    for chunk, index in game._item_blocks(html):
        m = re.search(r'href="(?:\.\./)*item/id/(\d+)"', chunk)
        name_m = re.search(r'item/id/\d+"><span>([^<]{2,60})</span>', chunk)
        out.append(
            {
                "index": index,
                "item_id": m.group(1) if m else "",
                "name": name_m.group(1).strip() if name_m else "",
                "mythic": "bonusdarkiron" in chunk,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--names", nargs="*", default=[])
    ap.add_argument("--send-to", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    config = load_config(ROOT / args.config)
    out: dict[str, object] = {"label": args.label or args.config}

    with tempfile.TemporaryDirectory(prefix="gear-transfer-") as tmp:
        game = Game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=120):
                out["error"] = "вход не подтверждён"
                print("GEAR_TRANSFER " + json.dumps(out, ensure_ascii=False), flush=True)
                return 1
            out["moved_to_bag"] = collect_new_items(game)
            bag = list_items(game, "https://barbars.ru/user/rack")
            store = list_items(game, "https://barbars.ru/user/public/store")
            out["bag"] = [b for b in bag if b["name"]]
            out["store"] = [s for s in store if s["name"]]
            if args.send_to:
                wanted = [n.lower() for n in args.names]
                picks = []
                for item in bag + store:
                    if not item["name"]:
                        continue
                    if wanted and not any(w in item["name"].lower() for w in wanted):
                        continue
                    picks.append(item)
                out["picks"] = picks
                sent = []
                for item in picks:
                    try:
                        ok = game.send_bag_item_to(args.send_to, item["item_id"])
                    except Exception as exc:  # noqa: BLE001
                        ok = f"ошибка: {exc}"
                    sent.append({"name": item["name"], "item_id": item["item_id"], "sent": ok})
                out["sent"] = sent
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("GEAR_TRANSFER " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
