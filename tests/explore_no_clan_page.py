"""Разбираем страницу «Без клана»: что за «(+)» и есть ли кнопка приглашения."""
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
    game.goto("https://barbars.ru/users/online?wicket:bookmarkablePage=:com.overmobile.combats.wicket.pages.online.GuildSearchPage")
    html = game.p.content()
    (ROOT / "knowledge" / "discovered" / "no-clan.html").write_text(html, encoding="utf-8")
    idx = html.find("Хотят в клан")
    print("=== фрагмент вокруг «Хотят в клан»")
    print(html[max(0, idx - 300) : idx + 2500])
    print("=== есть ли наш герой:", "fire white" in html.lower())
    for item in re.findall(r"[^\"'<>]{0,80}\(\+\)[^\"'<>]{0,80}", html):
        print("   plus:", " ".join(item.split())[:160])
finally:
    game.close()
