"""Дамп страниц торговли: аукцион ресурсов (лоты + форма выставления),
колодец удачи, мудрец, авторазбор. Нужен для написания точных селекторов."""

import json
import re
from pathlib import Path

from barbars.driver import Game

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
cfg["_root"] = str(ROOT)
game = Game(cfg, ROOT / "profile-test")
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)
game.start(headless=False)


def dump(name: str) -> str:
    html = game.p.content()
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
    (OUT / f"{name}.txt").write_text(game.body_text(), encoding="utf-8")
    return html


def show(name: str, pattern: str, limit: int = 2500, flags=re.S) -> None:
    html = (OUT / f"{name}.html").read_text(encoding="utf-8")
    m = re.search(pattern, html, flags)
    print(f"--- {name} / {pattern} ---")
    print((m.group(0)[:limit] if m else "НЕ НАЙДЕНО"))
    print()


try:
    if not game.ensure_login(timeout_sec=180):
        print("НЕ УДАЛОСЬ ВОЙТИ")
        raise SystemExit(1)

    # --- аукцион ресурсов: вкладки и лоты
    game.goto("https://barbars.ru/trade/bazaar")
    dump("bazaar-main")
    show("bazaar-main", r"<a[^>]*>[^<]*(Бутылочки|Мифрил|Железо|Мои лоты)[^<]*</a>")

    # лот бутылочек: как выглядит строка лота
    game.click_href("filterPotionsLink")
    dump("bazaar-bottles")
    show("bazaar-bottles", r".{300}бтл.{300}")
    show("bazaar-bottles", r"<a[^>]*>[^<]*купить[^<]*</a>")

    # лот мифрила
    game.click_href("filterMifrilLink")
    dump("bazaar-mifril")
    show("bazaar-mifril", r".{200}мфр.{200}")

    # --- форма выставления ресурсов
    game.goto("https://barbars.ru/trade/bazaar")
    game.click_text("Выставить ресурсы")
    dump("bazaar-form")
    show("bazaar-form", r"<form.{3000}")
    show("bazaar-form", r"<select.{1500}")
    show("bazaar-form", r"<input.{1500}")

    # --- колодец удачи
    game.goto("https://barbars.ru/trade/well")
    dump("well")
    show("well", r".{200}(Подарок|древнюю книгу|купить все|пожертвовать).{300}")

    # --- мудрец (опыт за железо)
    game.goto("https://barbars.ru/trade/ironmaster")
    dump("ironmaster")
    show("ironmaster", r".{300}(опыт|желез).{400}")

    # --- авторазбор
    game.goto("https://barbars.ru/user/rack/autocrack")
    dump("autocrack")
    show("autocrack", r".{300}(разобрать|Не разбирать).{400}")
finally:
    game.close()
