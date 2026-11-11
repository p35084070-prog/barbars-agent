"""Разведка «Управление кланом»: приглашения и назначение ролей."""
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
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)


def dump_links(game: Game, title: str) -> None:
    print(f"=== ссылки: {title} ===")
    for href, text in game.p.eval_on_selector_all(
        "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,45)])"
    ):
        print(f"   {href}   | {text}")


def dump_forms(game: Game) -> None:
    print("=== поля форм ===")
    for form in game.p.eval_on_selector_all(
        "form",
        "els => els.map(e => [e.getAttribute('action'), e.getAttribute('id'), "
        "[...e.querySelectorAll('input,select,textarea')].map(i => "
        "[i.tagName, i.getAttribute('name'), i.getAttribute('type'), i.getAttribute('value')])])",
    ):
        print("   form:", form)


game = Game(config, profile)
game.start(headless=True)
try:
    game.ensure_login(timeout_sec=120)
    game.goto("https://barbars.ru/guild/16675")
    print("клик «Управление кланом»:", game.click_text("Управление кланом", tags=("a", "span", "div")))
    print("url:", game.p.url)
    print("текст:", " ".join(game.body_text().split())[:1200])
    dump_links(game, "управление")
    dump_forms(game)
    html = game.p.content()
    (OUT / "clan-manage.html").write_text(html, encoding="utf-8")
    for pat in ("приглаш", "invite", "генерал", "назнач", "должност", "звать", "новый игрок", "регистрац"):
        found = re.findall(rf"[^\"'<>]{{0,90}}{pat}[^\"'<>]{{0,90}}", html, re.IGNORECASE)
        if found:
            print(f"--- «{pat}»:")
            for item in list(dict.fromkeys(found))[:8]:
                print("   ", " ".join(item.split())[:170])
finally:
    game.close()
