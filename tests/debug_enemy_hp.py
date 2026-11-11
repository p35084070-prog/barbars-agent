"""Отладка: разметка блока противника на боевой странице."""

import json
import re
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=False)
try:
    game.goto("https://barbars.ru/game/duel")
    html = game.p.content()
    # вырежем кусок вокруг строки с числом здоровья противника
    numbers = re.findall(r"<span[^>]*>([\d.,]+[kKmMgG]?)</span>", html)
    print("ВСЕ ЧИСЛА В SPAN:", numbers)
    for m in re.finditer(r"life\.png", html):
        print("--- life.png context ---")
        print(html[max(0, m.start() - 400) : m.start() + 300].replace("\n", " "))
        print()
    print("=== ICONS ===")
    for img in game.p.locator("img").all():
        src = img.get_attribute("src") or ""
        if any(k in src for k in ("life", "energy", "avatar", "user")):
            print(src, "|", (img.get_attribute("alt") or ""))
finally:
    game.close()
