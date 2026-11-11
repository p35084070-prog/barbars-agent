"""Ищет кнопку «Пригласить в клан» на странице игрока и в списке онлайна."""
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
        "https://barbars.ru/user/id/1596900",
        "https://barbars.ru/users/online",
        "https://barbars.ru/rating/stats",
    ):
        game.goto(url)
        print(f"=== {url}")
        print("текст:", " ".join(game.body_text().split())[:500])
        html = game.p.content()
        for pat in ("приглаш", "invite", "в клан", "добав"):
            found = re.findall(rf"[^\"'<>]{{0,80}}{pat}[^\"'<>]{{0,80}}", html, re.IGNORECASE)
            if found:
                print(f"--- «{pat}»:")
                for item in list(dict.fromkeys(found))[:6]:
                    print("   ", " ".join(item.split())[:160])
        print("--- ссылки (фильтр):")
        for href, text in game.p.eval_on_selector_all(
            "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
        ):
            if text and any(k in text.lower() for k in ("приглаш", "клан", "добав", "поиск", "найти")):
                print(f"   {href}   | {text}")
        print("--- формы:")
        for form in game.p.eval_on_selector_all(
            "form",
            "els => els.map(e => [e.getAttribute('action'), [...e.querySelectorAll('input,select')]"
            ".map(i => [i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
        ):
            print("   ", form)
finally:
    game.close()
