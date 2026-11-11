"""Отладка боевой страницы: снимок до хода, после удара и после умения."""

import json
import time
from pathlib import Path

from barbars.driver import Game

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=False)


def snap(title):
    print(f"===== {title} =====")
    print(game.body_text()[:1400])
    print("--- LINKS ---")
    for a in game.p.locator("a").all():
        text = (a.inner_text() or "").strip().replace("\n", " ")
        if text:
            print(repr(text), "|", (a.get_attribute("href") or "")[:70])


try:
    game.goto("https://barbars.ru/game/duel")
    snap("ПОСЛЕ ВХОДА В ДУЭЛЬ")
    cs = game.combat()
    print("=== COMBAT PARSE ===")
    print("our_hp:", cs.our_hp, "energy:", cs.our_energy, "enemy_hp:", cs.enemy_hp)
    print("enemy:", cs.enemy_name)
    print("attack:", cs.attack_links)
    print("heal:", cs.heal_links)
    print("flee:", cs.flee_links)
    print("potions:", cs.potion_links)
    print("abilities:", cs.abilities)
    print("log:", cs.log_lines)

    print(">>> кликаю умение")
    if cs.abilities:
        print("используем:", cs.abilities[0]["name"], cs.abilities[0]["href"][:60])
        game.use_ability(cs.abilities[0]["href"])
    snap("ПОСЛЕ УМЕНИЯ")

    print(">>> кликаю удар")
    game.click_attack()
    snap("ПОСЛЕ УДАРА")
    cs = game.combat()
    print("our_hp:", cs.our_hp, "energy:", cs.our_energy, "enemy_hp:", cs.enemy_hp)
    print("log:", cs.log_lines)
    time.sleep(4)
    game.reload()
    snap("ПОСЛЕ ПЕРЕЗАГРУЗКИ (регенерация)")
    cs = game.combat()
    print("our_hp:", cs.our_hp, "energy:", cs.our_energy, "enemy_hp:", cs.enemy_hp)
    print("abilities:", [(a["name"], a["ready"], a["desc"]) for a in cs.abilities])
finally:
    game.close()
