"""Вступает в клан новым аккаунтом: открывает страницу клана и жмёт «Вступить».

Запуск:
  python tests\\clan_join.py --profile profile-firewhite --guild 16675
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="profile-firewhite")
    parser.add_argument("--guild", default="16675")
    parser.add_argument("--config", default=str(ROOT / "config-firewhite.json"))
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    config["_root"] = str(ROOT)
    game = Game(config, ROOT / args.profile)
    game.start(headless=True)
    try:
        if not game.ensure_login(timeout_sec=180):
            print("НЕ УДАЛОСЬ войти в игру")
            return 1
        url = f"https://barbars.ru/guild/{args.guild}"
        game.goto(url)
        print("текст до:", " ".join(game.body_text().split())[:400])
        for word in ("Вступить", "Присоединиться", "Войти в клан", "Подать заявку", "Вступить в клан"):
            if game.click_text(word, tags=("a", "span", "div", "button", "input")):
                print(f"нажато: {word}")
                break
        else:
            print("кнопка вступления не найдена")
        game.goto(url)
        text = " ".join(game.body_text().split())
        print("текст после:", text[:600])
        print("В КЛАНЕ" if "Участники" in text and "Fire White" in text else "вступление не подтверждено")
        (ROOT / "knowledge" / "discovered" / "clan-join.html").write_text(game.p.content(), encoding="utf-8")
        return 0
    finally:
        game.close()


if __name__ == "__main__":
    sys.exit(main())
