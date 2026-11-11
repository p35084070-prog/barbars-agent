"""Проверка работы с рюкзаком: экипировка лучших вещей и сброс лишнего в сундук."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

CREDS = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt")


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in CREDS.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    config = {
        "base_url": "https://barbars.ru/",
        "profile_dir": str(ROOT / "profile-gear-test"),
        "headless": True,
        "auth": {"credentials_file": str(CREDS), "username_env": "", "password_env": ""},
        "humanize": {"enabled": False},
    }
    game = Game(config, config["profile_dir"])
    game.start(headless=True)
    try:
        if not game.ensure_login(timeout_sec=120):
            print("вход не удался")
            return 1
        print("рюкзак до:", game.bag_counts())
        t0 = time.time()
        worn = game.equip_better_items(limit=8)
        print(f"надето: {worn} за {time.time() - t0:.1f} c")
        print("рюкзак после экипировки:", game.bag_counts())
        t0 = time.time()
        moved = game.stash_items(keep=4)
        print(f"в сундук: {moved} за {time.time() - t0:.1f} c")
        print("рюкзак после сброса:", game.bag_counts())
        hero = game.goto("https://barbars.ru/user")
        print("герой:", " ".join(game.body_text().split())[:300])
    finally:
        game.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
