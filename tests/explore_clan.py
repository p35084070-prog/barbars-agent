"""Разведка страницы клана: ищем ссылку приглашения и список разделов."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
profile = ROOT / config.get("profile_dir", "profile")

game = Game(config, profile)
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    print("авторизация:", game.is_authenticated())
    game.goto("https://barbars.ru/")
    print("=== главная: ссылки ===")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
    ):
        print(f"   {href}   | {text}")

    print("=== иду в клан ===")
    if not game.click_href("guild"):
        game.click_text("клан", tags=("a", "span", "div", "li"))
    print("url:", game.p.url)
    print("текст:", " ".join(game.body_text().split())[:800])
    print("=== ссылки клана ===")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
    ):
        print(f"   {href}   | {text}")
    html = game.p.content()
    (ROOT / "knowledge" / "discovered").mkdir(parents=True, exist_ok=True)
    (ROOT / "knowledge" / "discovered" / "clan-page.html").write_text(html, encoding="utf-8")
    for pat in ("приглаш", "invite", "генерал", "general", "должност", "звать"):
        found = re.findall(rf"[^\"'<>]{{0,80}}{pat}[^\"'<>]{{0,80}}", html, re.IGNORECASE)
        if found:
            print(f"--- по слову «{pat}»:")
            for item in dict.fromkeys(found):
                print("   ", " ".join(item.split())[:160])
finally:
    game.close()
