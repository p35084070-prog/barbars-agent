"""Разведка: с какого уровня открывается аукцион (страница и справка игры).

Только чтение. Печатает уровень героя, текст торговых страниц и ссылки
справки, где может быть указан порог уровня.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402
from run import load_config, profile_dir  # noqa: E402

KEYWORDS = ("аукцион", "торгов", "лот", "рынок", "брокер", "торговл", "level", "уровн")


def build_game(config: dict, profile: Path):
    if config.get("ok_channel"):
        from barbars.ok_channel import OkGame

        return OkGame(config, profile)
    return Game(config, profile)


def main() -> int:
    parser = argparse.ArgumentParser(description="Пробник страниц торговли и справки")
    parser.add_argument("--config", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--urls", default="/trade/auctions,/trade/auction,/help")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    label = args.label or str(config.get("account") or args.config)
    out: dict[str, object] = {"label": label, "pages": {}}

    with tempfile.TemporaryDirectory(prefix=f"probe-{label}-") as tmp:
        game = build_game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=args.timeout):
                out["error"] = "вход не подтверждён"
                print("PROBE_PAGES " + json.dumps(out, ensure_ascii=False), flush=True)
                return 1
            try:
                hero = game.hero()
                out["hero_id"] = str(getattr(game, "hero_id", "") or "")
                out["level"] = getattr(hero, "level", None)
                out["hero_class"] = getattr(hero, "klass", "")
            except Exception as exc:  # noqa: BLE001
                out["hero_error"] = str(exc).splitlines()[0][:200]

            for url in [u.strip() for u in args.urls.split(",") if u.strip()]:
                page: dict[str, object] = {}
                try:
                    game.goto(url)
                    text = " ".join(game.body_text().split())
                    page["text_head"] = text[:600]
                    hits = [m.group(0) for m in re.finditer(r"[^.]{0,120}(?:уровен\w*|доступн\w*|открыва\w*)[^.]{0,120}", text, re.I)]
                    page["level_mentions"] = hits[:8]
                    links = []
                    for link in game.p.locator("a").all():
                        try:
                            label_text = " ".join((link.inner_text() or "").split())
                            href = link.get_attribute("href") or ""
                        except Exception:  # noqa: BLE001
                            continue
                        low = (label_text + " " + href).lower()
                        if "/help" in low or any(k in low for k in KEYWORDS):
                            links.append({"text": label_text[:70], "href": href[:110]})
                    page["links"] = links[:40]
                except Exception as exc:  # noqa: BLE001
                    page["error"] = str(exc).splitlines()[0][:200]
                out["pages"][url] = page
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("PROBE_PAGES " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
