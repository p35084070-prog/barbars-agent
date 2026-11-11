"""Разбор настроек клана: формы и поля (ищем добавление приглашающего/приглашение)."""
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
    game.goto("https://barbars.ru/guild/settings/0/16675")
    print("=== формы")
    for form in game.p.eval_on_selector_all(
        "form",
        "els => els.map(e => [e.getAttribute('action'), e.getAttribute('id'), [...e.querySelectorAll('input,select,textarea')]"
        ".map(i => [i.tagName, i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
    ):
        print("   ", form)
    print("=== input/select/button")
    html = game.p.content()
    for tag in re.findall(r"<(?:input|select|button|textarea)[^>]*>", html, re.I):
        print("   ", " ".join(tag.split()))
    print("=== select options")
    for block in re.findall(r"<select[^>]*>.*?</select>", html, re.I | re.S):
        for opt in re.findall(r"<option[^>]*>", block, re.I):
            print("   ", " ".join(opt.split()))
    print("=== текст")
    print("   ", " ".join(game.body_text().split())[:800])
finally:
    game.close()
