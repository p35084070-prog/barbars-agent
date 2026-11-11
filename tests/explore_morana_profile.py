"""Смотрим профиль игрока, который «хочет в клан» — ищем кнопку приглашения."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
game = Game(config, ROOT / config.get("profile_dir", "profile"))
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    for uid in ("4594065", "110387", "31389473"):
        game.goto(f"https://barbars.ru/user/id/{uid}")
        print(f"=== user/id/{uid}")
        print("текст:", " ".join(game.body_text().split())[:300])
        for href, text in game.p.eval_on_selector_all(
            "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,50)])"
        ):
            print(f"   {href}   | {text}")
        html = game.p.content()
        for item in re.findall(r"[^\"'<>]{0,60}(?:invite|Приглаш|приглаш|в клан)[^\"'<>]{0,60}", html, re.I):
            print("    html:", " ".join(item.split())[:160])
finally:
    game.close()
