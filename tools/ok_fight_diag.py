"""Диагностика боевой страницы в канале ОК.

Открывает игру, заходит в бой и печатает: ссылки умений, боевые кнопки, лог
боя. Затем нажимает одно умение и печатает страницу снова — так видно,
применяется ли умение вообще.

Запуск:
    python tools\ok_fight_diag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from barbars import pages  # noqa: E402
from barbars.ok_channel import OkGame  # noqa: E402


def dump(game: OkGame, title: str) -> str:
    text = game.body_text()
    print(f"\n===== {title} =====")
    print(" | ".join(line.strip() for line in text.splitlines() if line.strip())[:1800])
    return text


def main() -> int:
    config = json.loads((ROOT / "config-ok.json").read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = OkGame(config, ROOT / "profile-ok-navtest")
    try:
        game.start(headless=True)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ игра не открылась: {exc}")
        return 1

    game.goto("https://barbars.ru/")
    targets = pages.home_targets(game)
    print("цели с главной:")
    for t in targets:
        print(f"  {t.title!r} kind={t.kind} осталось={t.fights_left} href={t.href}")
    if not targets:
        print("целей нет — уходим")
        game.close()
        return 1

    pick = next((t for t in targets if t.fights_left and t.fights_left > 0), targets[0])
    print(f"\nидём в бой: {pick.title} ({pick.href})")
    game.goto(pick.href)
    dump(game, "бой до действия")

    print("\nумения:")
    abilities = game.p.locator("a[href*='abilityCombatPanel']").all()
    for a in abilities:
        try:
            print(f"  {(a.inner_text() or '').strip()[:90]!r} -> {a.get_attribute('href')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  <ошибка: {exc}>")
    if not abilities:
        print("  умений не найдено")
    print("\nбоевые кнопки:")
    for link in game.p.locator("a").all():
        try:
            text = (link.inner_text() or "").strip().split("\n")[0]
        except Exception:  # noqa: BLE001
            continue
        if text.startswith(("Бить", "Лечить", "Сбежать", "Отступить", "Убежать", "Атаковать")):
            print(f"  {text!r}")

    if abilities:
        href = abilities[0].get_attribute("href") or ""
        print(f"\nнажимаем умение: {href}")
        ok = game.use_ability(href)
        print(f"use_ability -> {ok}")
        # тот же клик, но с печатью ошибки — понять, что именно не срабатывает
        selector = "a[href*='" + href + "']"
        print(f"совпадений по селектору: {game.p.locator(selector).count()}")
        target = game.p.locator(selector).first
        try:
            print("visible:", target.is_visible(), "| box:", target.bounding_box())
            target.scroll_into_view_if_needed(timeout=3000)
            print("scroll ok")
            target.click(timeout=8000)
            print("click ok")
        except Exception as exc:  # noqa: BLE001
            print(f"ОШИБКА клика: {type(exc).__name__}: {str(exc)[:400]}")
        dump(game, "бой после умения")

    game.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
