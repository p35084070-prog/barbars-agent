"""Выбросить из сундука/рюкзака бесполезный хлам.

Логика (по решению игрока от 16.11.2026):
- вещь защищённого качества (мифическая/легендарная/эпическая) — НЕ трогаем;
- вещь с пометкой «Лучше (+N)» — её надо надеть, а не выбросить;
- остальное: если на странице вещи есть «разобрать на …» (`crackLink`) — разбираем
  (железо идёт на ремонт), если только «выкинуть» (`dropLink`) — выбрасываем:
  с такой вещи даже железо получить нельзя, держать её незачем.

Запуск:
    python tools\\drop_junk.py --config deploy\\config-actions-steelblue.json \
        --creds credentials\\steelblue.txt [--where chest|bag|both] [--dry-run]
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

from barbars import pages  # noqa: E402
from barbars.driver import Game  # noqa: E402
from run import load_config  # noqa: E402

PROTECTED = ("мифический", "легендарн", "эпическ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--where", default="chest", choices=["chest", "bag", "both"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    config = load_config(ROOT / args.config)
    creds = Path(args.creds)
    if not creds.is_absolute():
        creds = ROOT / creds

    out: dict[str, object] = {"dropped": [], "cracked": [], "skipped": [], "errors": []}

    with tempfile.TemporaryDirectory(prefix="dropjunk-", ignore_cleanup_errors=True) as tmp:
        game = Game(config, Path(tmp))
        game.start(headless=True)
        if not game.ensure_login(timeout_sec=120):
            print("DROP_JUNK " + json.dumps({"error": "вход не подтверждён"}, ensure_ascii=False))
            return 1

        targets: list[tuple[str, str, str, str]] = []  # (где, id, имя, тир)
        urls = []
        if args.where in ("chest", "both"):
            urls.append(("chest", "https://barbars.ru/user/store"))
        if args.where in ("bag", "both"):
            urls.append(("bag", "https://barbars.ru/user/rack"))

        for where, url in urls:
            game.goto(url)
            html = game.p.content()
            for chunk, _index in game._item_blocks(html):
                item_id = re.search(r"item/id/(\d+)", chunk)
                if not item_id:
                    continue
                name_m = re.search(r">\s*([^<>]{2,40})\s*</span>", chunk)
                name = name_m.group(1).strip() if name_m else "?"
                tier = pages.item_tier(chunk) or "обычный"
                targets.append((where, item_id.group(1), name, tier))

        for where, item_id, name, tier in targets[: args.limit]:
            low_tier = tier.lower()
            if any(p in low_tier for p in PROTECTED):
                out["skipped"].append({"name": name, "tier": tier, "why": "защищённое качество"})
                continue
            game.goto(f"https://barbars.ru/item/id/{item_id}")
            html = game.p.content()
            body = " ".join(game.body_text().split())
            if "Вещь не найдена" in body:
                out["skipped"].append({"name": name, "tier": tier, "why": "вещи нет"})
                continue
            if "Лучше" in body:
                out["skipped"].append({"name": name, "tier": tier, "why": "«Лучше» — надо надеть"})
                continue
            if args.dry_run:
                out["skipped"].append(
                    {
                        "name": name,
                        "tier": tier,
                        "why": "разобрать" if "crackLink" in html else "выкинуть",
                    }
                )
                continue
            if "crackIronPanel:crackLink" in html:
                # с этой вещи можно получить железо — такие не выбрасываем
                # (правило игрока: дубли вещей не трогаем)
                out["skipped"].append({"name": name, "tier": tier, "why": "разбирается на железо — оставляем"})
            elif "crackIronPanel:dropLink" in html:
                ok = game.click_href("crackIronPanel:dropLink")
                game._settle()
                if ok:
                    out["dropped"].append({"name": name, "tier": tier, "id": item_id})
                else:
                    out["errors"].append({"name": name, "why": "выкинуть не вышло"})
            else:
                out["skipped"].append({"name": name, "tier": tier, "why": "нет действий"})

    print("DROP_JUNK " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
