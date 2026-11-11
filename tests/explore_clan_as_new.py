"""Страница клана глазами нового героя: ищем способ вступить."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

config = json.loads((ROOT / "config-firewhite.json").read_text(encoding="utf-8"))
config["_root"] = str(ROOT)
game = Game(config, ROOT / "profile-firewhite")
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    game.goto("https://barbars.ru/guild/16675")
    print("текст:", " ".join(game.body_text().split())[:900])
    print("=== ссылки")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,45)])"
    ):
        print(f"   {href}   | {text}")
    print("=== формы")
    for form in game.p.eval_on_selector_all(
        "form",
        "els => els.map(e => [e.getAttribute('action'), [...e.querySelectorAll('input,select')]"
        ".map(i => [i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
    ):
        print("   ", form)
    print("=== input/button")
    html = game.p.content()
    for tag in re.findall(r"<(?:input|button)[^>]*>", html, re.I):
        print("   ", " ".join(tag.split()))
    print("=== упоминания вступ/заявк/join")
    for item in re.findall(r"[^\"'<>]{0,70}(?:вступ|заявк|join|invite|Приглаш)[^\"'<>]{0,70}", html, re.I):
        print("   ", " ".join(item.split())[:150])
finally:
    game.close()
