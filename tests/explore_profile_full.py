"""Полный разбор страницы профиля героя (ищем кнопку приглашения в клан)."""
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
    game.goto("https://barbars.ru/user/id/31389504")
    html = game.p.content()
    (ROOT / "knowledge" / "discovered" / "profile-firewhite.html").write_text(html, encoding="utf-8")
    print("=== все ссылки")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,45)])"
    ):
        print(f"   {href}   | {text}")
    print("=== кнопки/input")
    for tag in re.findall(r"<(?:input|button)[^>]*>", html, re.I):
        print("   ", " ".join(tag.split()))
    print("=== упоминания guild/invite")
    for item in re.findall(r"[^\"'<>]{0,60}(?:invite|guild|Invite)[^\"'<>]{0,60}", html):
        print("   ", " ".join(item.split())[:140])
finally:
    game.close()
