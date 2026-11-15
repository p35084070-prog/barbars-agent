"""Забрать почту, собрать вещи в рюкзак и надеть лучшее снаряжение.

Используется для пятого героя: после отправки комплекта почтой он забирает
посылку и надевает вещи (экипировка работает только при `gear.auto_equip`).

Запуск:
    python tools\\equip_hero.py --config deploy\\config-actions-steelblue.json \
        --hero-id 31390082 [--equip]
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


def collect_new_items(game: Game, limit: int = 30) -> int:
    """Перенести вещи из панели «новый предмет» в рюкзак."""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--hero-id", required=True)
    ap.add_argument("--equip", action="store_true", help="надеть вещи с пометкой «Лучше»")
    args = ap.parse_args()

    config = load_config(ROOT / args.config)
    out: dict[str, object] = {"config": args.config}

    with tempfile.TemporaryDirectory(prefix="equip-hero-") as tmp:
        game = Game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=120):
                out["error"] = "вход не подтверждён"
                print("EQUIP_HERO " + json.dumps(out, ensure_ascii=False), flush=True)
                return 1
            game.goto("https://barbars.ru/user/rack")
            out["rack_text"] = " ".join(game.body_text().split())[:200]
            # освобождаем рюкзак: иначе посылки не влезают
            out["stashed"] = game.stash_items(keep=2, limit=20)
            out["cracked"] = game.crack_items(limit=20)
            game.goto("https://barbars.ru/user/mail")
            out["mail_text"] = " ".join(game.body_text().split())[:600]
            links = []
            for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', game.p.content(), re.S | re.I):
                label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
                href = m.group(1)
                if re.search(r"посылк|забр|mail|message|get", href + " " + label, re.I):
                    links.append({"label": label[:60], "href": href[:120]})
            out["mail_links"] = links[:40]
            out["mail_taken"] = game.take_mail()
            game.goto("https://barbars.ru/user/mail")
            out["mail_text_after"] = " ".join(game.body_text().split())[:600]
            mail_html = game.p.content()
            # каждую посылку надо открыть и забрать отдельной кнопкой
            parcels = re.findall(r'href="(?:\.\./)*user/mail/message/id/(\d+)"', mail_html)
            out["parcels"] = parcels[:30]
            taken = []
            for pid in parcels[:30]:
                game.goto(f"https://barbars.ru/user/mail/message/id/{pid}")
                ok = game.click_href("getLink")
                game._settle()
                taken.append({"id": pid, "ok": bool(ok)})
            out["parcels_taken"] = taken
            game.goto("https://barbars.ru/user/mail")
            out["mail_text_final"] = " ".join(game.body_text().split())[:600]
            out["moved_to_bag"] = collect_new_items(game)
            bag = game.bag_items()
            out["bag"] = [{"id": i["item_id"], "name": i["name"], "better": i["better"]} for i in bag if i["name"]]
            if args.equip:
                out["worn_count"] = game.equip_better_items(limit=12)
                # мифические вещи без метки «Лучше» (герой ниже уровня вещи)
                # надеваем напрямую — слот занять должна новая вещь
                forced = []
                for item in game.bag_items():
                    if not item["mythic"] or not item["name"]:
                        continue
                    ok = game.click_href(f"items:{item['index']}:wearLink")
                    game.confirm_if_needed()
                    game._settle()
                    forced.append({"name": item["name"], "ok": bool(ok)})
                out["forced_equip"] = forced
            game.goto(f"https://barbars.ru/user/body/id/{args.hero_id}")
            out["worn_text"] = " ".join(game.body_text().split())[:1200]
            st = game.status()
            out["hero_level"] = getattr(st, "level", None)
            out["hero_text"] = " ".join(game.body_text().split())[:300]
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("EQUIP_HERO " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
