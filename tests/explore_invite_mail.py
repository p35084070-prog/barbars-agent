"""Ищем приглашение в клан: внутренняя почта и чат клана."""
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
    for url in (
        "https://barbars.ru/user/mail/send/id/31389504",
        "https://barbars.ru/guild/chat",
        "https://barbars.ru/chat",
    ):
        game.goto(url)
        print(f"=== {url}")
        print("текст:", " ".join(game.body_text().split())[:500])
        html = game.p.content()
        print("--- формы")
        for form in game.p.eval_on_selector_all(
            "form",
            "els => els.map(e => [e.getAttribute('action'), [...e.querySelectorAll('input,select,textarea')]"
            ".map(i => [i.tagName, i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
        ):
            print("   ", form)
        print("--- ссылки (подозрительные)")
        for href, text in game.p.eval_on_selector_all(
            "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,45)])"
        ):
            if any(k in (href or "").lower() + text.lower() for k in ("invit", "приглаш", "guild", "clan")):
                print("   ", href, "|", text)
        for item in re.findall(r"[^\"'<>]{0,60}(?:invit|Приглаш|приглаш)[^\"'<>]{0,60}", html):
            print("    html:", " ".join(item.split())[:140])
finally:
    game.close()
