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
            text = game.body_text()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            out["lines_matched"] = [l for l in lines if KEY.search(l)][:40]
            out["head"] = lines[:12]
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
