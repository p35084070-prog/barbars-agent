"""Дамп HTML алтаря: как оформлены варианты пожертвования."""

import json
import re
from pathlib import Path

from barbars.driver import Game

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(ROOT)
game = Game(cfg, ROOT / "profile-test")
OUT = ROOT / "knowledge" / "discovered"
game.start(headless=False)
try:
    if not game.ensure_login(timeout_sec=180):
        print("НЕ УДАЛОСЬ ВОЙТИ")
        raise SystemExit(1)
    game.ensure_guild_id()
    game.goto(f"https://barbars.ru/guild/altar/0/{game.guild_id}")
    html = game.p.content()
    (OUT / "altar.html").write_text(html, encoding="utf-8")
    for match in re.finditer(r".{200}Пожертвовать.{200}", html, re.S):
        print(re.sub(r"\s+", " ", match.group(0)))
        print("---")
finally:
    game.close()
