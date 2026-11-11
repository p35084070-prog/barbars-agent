"""Детальный обзор: что реально фармово и сколько стоит."""

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
    ("duel", "https://barbars.ru/game/duel"),
    ("dungeons-common", "https://barbars.ru/game/dungeons/1/1"),
    ("dungeons-clan", "https://barbars.ru/game/dungeons/2/1"),
    ("dungeons-trial", "https://barbars.ru/game/dungeons/3/1"),
    ("contest1", "https://barbars.ru/game/contest/0/1"),
    ("contest5", "https://barbars.ru/game/contest/0/5"),
    ("towers-map", "https://barbars.ru/game/towers/map"),
    ("battle", "https://barbars.ru/game/battle"),
    ("castle6", "https://barbars.ru/castle/6"),
    ("dragon", "https://barbars.ru/game/dragonDungeon"),
    ("greatboss", "https://barbars.ru/game/greatBoss"),
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
        text = game.body_text()
        (OUT / f"act-{name}.txt").write_text(text, encoding="utf-8")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        print("  ТЕКСТ:", " | ".join(lines[2:26])[:900])
        print("  КНОПКИ/ССЫЛКИ:")
        for a in game.p.locator("a").all():
            try:
                t = (a.inner_text() or "").strip().replace("\n", " ")
                href = a.get_attribute("href") or ""
            except Exception:
                continue
            if not t:
                continue
            if re.search(
                r"(бить|атаков|бой|в очеред|начать|идти|в бой|встать|напад|штурм|захват|драться|вызов|появиться|выбери|войти|заявиться|идти в бой)",
                t,
                re.I,
            ):
                print(f"    - {t[:70]!r} -> {href[:100]}")
finally:
    game.close()
