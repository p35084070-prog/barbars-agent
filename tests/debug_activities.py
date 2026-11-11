"""Обзор всех игровых активностей: что доступно, какие кнопки боя, есть ли платные ограничения."""

import json
import re
from pathlib import Path

from barbars.driver import Game

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(ROOT)
game = Game(cfg, ROOT / "profile-test")
OUT = ROOT / "knowledge" / "discovered"

PAGES = [
    ("dungeons", "https://barbars.ru/game/dungeons"),
    ("tower", "https://barbars.ru/game/ogreDungeon"),
    ("duel", "https://barbars.ru/game/duel"),
    ("arena", "https://barbars.ru/game/arena"),
    ("survival", "https://barbars.ru/game/survival"),
    ("greats", "https://barbars.ru/games/greats"),
    ("contests", "https://barbars.ru/game/contests"),
    ("castles", "https://barbars.ru/castles"),
    ("towers", "https://barbars.ru/game/towers"),
]

game.start(headless=False)
try:
    if not game.ensure_login(timeout_sec=180):
        print("НЕ УДАЛОСЬ ВОЙТИ")
        raise SystemExit(1)

    for name, url in PAGES:
        print("=" * 70)
        print(f"### {name}  {url}")
        try:
            game.goto(url)
        except Exception as exc:
            print("  ОШИБКА:", exc)
            continue
        html = game.p.content()
        (OUT / f"act-{name}.html").write_text(html, encoding="utf-8")
        (OUT / f"act-{name}.txt").write_text(game.body_text(), encoding="utf-8")
        lines = [l.strip() for l in game.body_text().splitlines() if l.strip()]
        print("  ТЕКСТ:", " | ".join(lines[2:22])[:700])
        print("  ССЫЛКИ:")
        for a in game.p.locator("a").all():
            try:
                text = (a.inner_text() or "").strip().replace("\n", " ")
                href = a.get_attribute("href") or ""
            except Exception:
                continue
            if not text or not href:
                continue
            if re.search(r"(fightmore|dungeon|ogre|duel|arena|survival|great|contest|castle|tower|battle|start)", href, re.I):
                print(f"    - {text[:60]!r} -> {href[:110]}")
finally:
    game.close()
