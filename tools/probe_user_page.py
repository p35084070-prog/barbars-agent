"""Разведка страницы героя: как пишется усталость (для сторожа башен).

Печатает строки страницы, где есть «устал/вынос/башн», и первые строки текста.
Только чтение.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402
from run import load_config  # noqa: E402

KEY = re.compile(r"устал|вынос|башн|труд|отдых|%|железо|мифрил", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--url", default="/user")
    parser.add_argument("--click-location", action="store_true",
                        help="перейти в локацию башни и снять страницу боя")
    parser.add_argument("--click-text", action="append", default=[],
                        help="кликнуть по ссылке с этим текстом (можно несколько раз)")
    parser.add_argument("--wait-after", type=int, default=0,
                        help="сколько секунд ждать после последнего клика")
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    label = args.label or str(config.get("account") or args.config)
    out: dict[str, object] = {"label": label, "url": args.url}

    with tempfile.TemporaryDirectory(prefix=f"probe-{label}-") as tmp:
        game = None
        if config.get("ok_channel"):
            from barbars.ok_channel import OkGame

            game = OkGame(config, Path(tmp))
        else:
            game = Game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=120):
                out["error"] = "вход не подтверждён"
                print("PROBE_USER " + json.dumps(out, ensure_ascii=False), flush=True)
                return 1
            game.goto("https://barbars.ru" + args.url)
            if args.click_location:
                loc = game.p.locator("a[href*='locationLink']")
                if loc.count():
                    try:
                        loc.first.click(timeout=8000)
                        game._settle()
                        out["clicked_location"] = " ".join((loc.first.inner_text() or "").split())
                    except Exception as exc:  # noqa: BLE001
                        out["click_error"] = str(exc).splitlines()[0][:200]
                else:
                    out["click_error"] = "нет ссылок локаций"
            text = game.body_text()
            for wanted in args.click_text:
                loc = game.p.locator(f"a:has-text('{wanted}'), button:has-text('{wanted}')")
                if loc.count():
                    try:
                        loc.first.click(timeout=8000)
                        game._settle()
                        out.setdefault("clicked_text", []).append(wanted)
                    except Exception as exc:  # noqa: BLE001
                        out.setdefault("click_errors", []).append(f"{wanted}: {str(exc).splitlines()[0][:120]}")
                else:
                    out.setdefault("click_errors", []).append(f"{wanted}: не найдено")
            if args.wait_after:
                time.sleep(args.wait_after)
                text = game.body_text()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            out["lines_matched"] = [l for l in lines if KEY.search(l)][:40]
            out["head"] = lines[:12]
            if "bg" in args.url:
                from barbars import pages

                out["battlefields"] = pages.parse_battlefields(game.p.content(), text)
            links = []
            for link in game.p.locator("a").all():
                try:
                    links.append({
                        "text": " ".join((link.inner_text() or "").split())[:60],
                        "href": (link.get_attribute("href") or "")[:90],
                    })
                except Exception:  # noqa: BLE001
                    continue
            out["all_links"] = links
            out["inputs"] = [
                {"name": el.get_attribute("name"), "type": el.get_attribute("type"),
                 "value": (el.get_attribute("value") or "")[:40]}
                for el in game.p.locator("input").all()
            ]
            out["buttons"] = [
                {"text": " ".join((b.inner_text() or "").split())[:50],
                 "name": b.get_attribute("name"), "value": (b.get_attribute("value") or "")[:30]}
                for b in game.p.locator("button").all()
            ]
            try:
                out["fatigue_api"] = game.hero_fatigue()
            except Exception as exc:  # noqa: BLE001
                out["fatigue_error"] = str(exc).splitlines()[0][:200]
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("PROBE_USER " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
