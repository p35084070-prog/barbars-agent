"""Ищет героя через «Поиск» и приглашает в клан (от лидера keis)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

NICK = sys.argv[1] if len(sys.argv) > 1 else "fire white ii"

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
game = Game(config, ROOT / config.get("profile_dir", "profile"))
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    game.goto("https://barbars.ru/users/search")
    print("страница поиска:", " ".join(game.body_text().split())[:400])
    for form in game.p.eval_on_selector_all(
        "form",
        "els => els.map(e => [e.getAttribute('action'), [...e.querySelectorAll('input,select')]"
        ".map(i => [i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
    ):
        print("форма:", form)

    filled = False
    for selector in ("input[name='login']", "input[name='name']", "input[type='text']", "input[name='search']"):
        if game.p.locator(selector).count():
            game.p.fill(selector, NICK, timeout=5000)
            print("заполнил", selector)
            filled = True
            break
    if filled:
        game.p.click("input[type='submit'], button:has-text('Найти'), button:has-text('Поиск')")
        game._settle()
    print("результат:", " ".join(game.body_text().split())[:600])
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
    ):
        if text and ("fire" in text.lower() or "white" in text.lower()):
            print("  найден:", href, "|", text)
            game.goto("https://barbars.ru/" + href.lstrip("/") if not href.startswith("http") else href)
            print("  профиль:", " ".join(game.body_text().split())[:400])
            for href2, text2 in game.p.eval_on_selector_all(
                "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
            ):
                if text2 and any(k in text2.lower() for k in ("приглаш", "клан", "добав")):
                    print("  кнопка:", href2, "|", text2)
            break
finally:
    game.close()
