"""Смотрит «Настройки» героя: смена ника/пароля, создание персонажа."""
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
    game.goto("https://barbars.ru/user/settings")
    print("текст:", " ".join(game.body_text().split())[:900])
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,45)])"
    ):
        print(f"   {href}   | {text}")
    print("--- поля форм ---")
    for form in game.p.eval_on_selector_all(
        "form",
        "els => els.map(e => [e.getAttribute('action'), [...e.querySelectorAll('input,select,textarea')]"
        ".map(i => [i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
    ):
        print("   form:", form)
    html = game.p.content()
    for pat in ("ник", "парол", "почт", "удал", "новый", "персонаж", "созда"):
        found = re.findall(rf"[^\"'<>]{{0,60}}{pat}[^\"'<>]{{0,60}}", html, re.IGNORECASE)
        if found:
            print(f"--- «{pat}»:")
            for item in list(dict.fromkeys(found))[:6]:
                print("   ", " ".join(item.split())[:140])
    (ROOT / "knowledge" / "discovered" / "user-settings.html").write_text(html, encoding="utf-8")
finally:
    game.close()
