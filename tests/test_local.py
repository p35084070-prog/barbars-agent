"""Локальные проверки парсеров и правил (без браузера)."""

import json
from pathlib import Path

from barbars.driver import parse_amount
from barbars import pages, rules
from barbars.llm import ClaudeAdvisor

config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))

# --- парсер чисел -------------------------------------------------
cases = {"52k": 52000, "1.96M": 1960000, "290": 290, "1070500": 1070500, "76": 76, "30.0M": 30000000}
for raw, expected in cases.items():
    got = parse_amount(raw)
    assert got == expected, f"{raw}: ожидалось {expected}, получено {got}"
print("parse_amount: ok")

# --- разбор боевой страницы (реальная разметка башни призраков) ---
fight_html = """
<table><tbody><tr><td><img src="/images/icons/life.png" alt=""><span>3698</span>
<img src="/images/icons/energy.png" alt=""><span>3429</span></td></tr></tbody></table>
<table><tbody><tr><td><img src="/images/icons/life.png" alt=""><span>49k</span></td></tr></tbody></table>
<div class="fbtn mb2"><a href="../?wicket:interface=:11:actionPanel:damageOgreLink::ILinkListener::">
<span class="lbl">Бить <span>разгневанного призрака</span><span>обычный удар</span></span></a></div>
<div class="fbtn mb2"><a href="../?wicket:interface=:11:actionPanel:abilityCombatPanel:ability:0:activateLink::ILinkListener::">
<span class="lbl"><span>Версерк</span> <span>(готово)</span><span>увеличивает урон</span></span></a></div>
<div class="fbtn mb2"><a href="../?wicket:interface=:11:actionPanel:abilityCombatPanel:ability:1:activateLink::ILinkListener::">
<span class="lbl"><span>Уворот</span> <span>(готово)</span><span>уворот от удара</span></span></a></div>
"""
Path("fight_sample.html").write_text(fight_html, encoding="utf-8")
print("образец боя сохранён: fight_sample.html")

# --- правила: приоритеты ------------------------------------------
state = rules.GameState(
    hp=1000, max_hp=3698, energy=3000, max_energy=3748, level=67, klass="медик",
    iron=1_000_000, mifril=40, gold=28, silver=76, bottles=290, talent_points=0,
    free_dungeon=2, free_duel=3,
    needs_repair=True, repair_cost=6,
    targets=[pages.FightTarget("Башня призраков", "game/ogreDungeon", "dungeon", 2),
             pages.FightTarget("Дуэли", "game/duel", "duel", 3)],
    quests=[pages.ClanQuest("Усиленная прокачка", "Заработай 100.0M опыта", "4 30.0M КО 1-5", 6)],
)
d = rules.decide(state, config)
assert d.action == "repair", d
state.needs_repair = False
state.iron = 0
d = rules.decide(state, config)
assert d.action == "quest", d
state.quests = []
d = rules.decide(state, config)
assert d.action == "fight" and d.params["href"] == "game/ogreDungeon", d
state.targets = []
state.iron = 1_000_000
state.altar_bonus = 0.0
state.altar_expires_in_min = 10
state.altar_options = [{"kind": "iron", "cost": 1250, "bonus": 12.5}]
d = rules.decide(state, config)
assert d.action == "altar", d  # починка не требуется — жертвуем в алтарь
state.iron = 100_000
d = rules.decide(state, config)
assert d.action == "altar", d
state.iron = 10_000  # ниже порога — жертвовать нечего
state.autocrack_set_today = True  # авторазбор уже настроен
state.farm_skip = [e["name"] for e in config["farm"]["events"]]  # фарм-события отключены
d = rules.decide(state, config)
assert d.action == "wait", d
# бонус не понижаем: при текущем +25% железо (+12,5%) не предлагаем
state.iron = 1_000_000
state.altar_bonus = 25.0
d = rules.decide(state, config)
assert d.action != "altar", d
print("decide: ok")

# --- рюкзак: разбор на железо и отсутствие зацикливания ------------
# Сундук полон (25/25), рюкзак 9/20: ничего не надеть и не разобрать.
# Шаг «рюкзак» не должен блокировать фарм, когда он бесполезен.
bag_state = rules.GameState(
    hp=1000, max_hp=4042, energy=4000, max_energy=4076, level=67, klass="медик",
    iron=518_754, gold=30, silver=21, talent_points=0,
    free_dungeon=0, free_duel=0,
    bag={"bag_used": 9, "bag_total": 20, "chest_used": 25, "chest_total": 25},
    gear_blocked=True,
)
bag_state.altar_bonus = 12.5
bag_state.altar_expires_in_min = 120
bag_state.well_gift_taken_today = True
bag_state.autocrack_set_today = True
bag_state.farm_skip = [e["name"] for e in config["farm"]["events"]]
d = rules.decide(bag_state, config)
assert d.action != "gear", f"шаг рюкзака не должен блокировать фарм: {d}"
# блокировка снята (например, пришёл новый дроп) — шаг рюкзака обязателен
bag_state.gear_blocked = False
bag_state.bag = {"bag_used": 9, "bag_total": 20, "chest_used": 10, "chest_total": 25}
d = rules.decide(bag_state, config)
assert d.action == "gear", d
assert d.params["crack"] is True, d  # по новому правилу остальное — на железо
# рюкзак и сундук полны: сначала ручной разбор, авторазбор — только если ручного нет
bag_state.bag = {"bag_used": 20, "bag_total": 20, "chest_used": 25, "chest_total": 25}
bag_state.autocrack_kind = ""
d = rules.decide(bag_state, config)
assert d.action == "gear", d
cfg_no_crack = json.loads(json.dumps(config))
cfg_no_crack["gear"]["crack"] = False
d = rules.decide(bag_state, cfg_no_crack)
assert d.action == "autocrack", d
# рюкзак пуст, но сундук полон — чистим сундук (там копится старый хлам)
bag_state.gear_blocked = False
bag_state.bag = {"bag_used": 0, "bag_total": 20, "chest_used": 20, "chest_total": 20}
d = rules.decide(bag_state, config)
assert d.action == "gear", d
print("gear loop: ok")

# --- магазин снаряжения: выбор по максимальным характеристикам --------
shop_items = [
    {"name": "Шлем Берсерка", "level": 25, "bonus": 179, "gold": 0, "silver": 55, "tier": "мифический", "href": "trade/auction/shop/item/id/1"},
    {"name": "Перчатки Берсерка", "level": 25, "bonus": 400, "gold": 2, "silver": 0, "tier": "мифический", "href": "trade/auction/shop/item/id/2"},
    {"name": "Топор Берсерка", "level": 25, "bonus": 305, "gold": 0, "silver": 55, "tier": "мифический", "href": "trade/auction/shop/item/id/3"},
    {"name": "Копье Голиафа", "level": 25, "bonus": 316, "gold": 0, "silver": 55, "tier": "мифический", "href": "trade/auction/shop/item/id/4"},
    {"name": "Шлем Ветерана", "level": 25, "bonus": 250, "gold": 0, "silver": 55, "tier": "мифический", "href": "trade/auction/shop/item/id/5"},
    {"name": "Амулет Берсерка", "level": 25, "bonus": 371, "gold": 6, "silver": 30, "tier": "мифический", "href": "trade/auction/shop/item/id/6"},
]
worn = [{"name": "Секира Воина", "slot": "оружие"}, {"name": "Шлем Воина", "slot": "шлем"}]
picked = pages.pick_shop_items(shop_items, worn, max_gold=3)
names = [p["name"] for p in picked]
assert "Перчатки Берсерка" in names, names          # 2 золота, +400 — берём
assert "Шлем Ветерана" in names, names              # по слоту «шлем» максимум +250 > +179
assert "Шлем Берсерка" not in names, names          # проигрывает по бонусу
assert "Топор Берсерка" not in names, names         # оружие другого типа
assert "Копье Голиафа" not in names, names          # оружие другого типа
assert "Амулет Берсерка" not in names, names         # 6 золота > лимита 3
# уже купленный слот пропускаем
picked2 = pages.pick_shop_items(shop_items, worn, max_gold=3, bought_slots=["шлем", "перчатки"])
assert not [p for p in picked2 if p["name"].startswith("Шлем")], picked2
print("shop pick: ok")

# --- прокачка параметров железом ----------------------------------
up_state = rules.GameState(
    hp=1000, max_hp=4042, energy=4000, max_energy=4076, level=14, klass="воин",
    iron=100_000, mifril=0, gold=0, silver=0, talent_points=0,
    free_dungeon=0, free_duel=0,
    bag={"bag_used": 0, "bag_total": 20, "chest_used": 0, "chest_total": 20},
)
up_state.altar_bonus = 12.5
up_state.altar_expires_in_min = 120
up_state.well_gift_taken_today = True
up_state.autocrack_set_today = True
up_state.farm_skip = [e["name"] for e in config["farm"]["events"]]
up_state.master_options = [
    {"param": "strength", "cost": 10_000, "gain": 8, "currency": "iron",
     "href": "moreParamsPanel:strength:upBlock:upLink"},
    {"param": "health", "cost": 100, "gain": 24, "currency": "gold",
     "href": "moreParamsPanel:health:upBlock:upLink"},
]
d = rules.decide(up_state, config)
assert d.action == "upgrade", d
assert d.target == "strength", d  # золотой вариант пропускаем
# железа не хватает (оставляем запас) — прокачки нет
up_state.iron = 50_000
d = rules.decide(up_state, config)
assert d.action != "upgrade", d
# уровень мастерства: 35K железа + 200 мифрила
up_state.iron = 100_000
up_state.mifril = 300
up_state.mastery_cost = {"iron": 35_000, "mifril": 200}
d = rules.decide(up_state, config)
assert d.action == "upgrade_mastery", d
up_state.mifril = 100  # мифрила не хватает
d = rules.decide(up_state, config)
assert d.action == "upgrade", d  # вернулись к прокачке параметра
print("upgrade: ok")

# --- боевая политика ----------------------------------------------
cs = rules.CombatState(our_hp=1000, our_energy=3748, enemy_hp=49000,
                        attack_links=["Бить разгневанного призрака"],
                        abilities=[{"name": "Версерк", "ready": True, "desc": "увеличивает урон", "href": "ability:0"},
                                   {"name": "Каменный щит", "ready": True, "desc": "уменьшает урон", "href": "ability:2"}])
policy = rules.CombatPolicy(config)
st = rules.GameState(max_hp=3698, max_energy=3748)
choice = policy.choose(cs, st, st)
assert choice.action == "ability" and choice.target == "Версерк", choice
cs.abilities = []
choice = policy.choose(cs, st, st)
assert choice.action == "attack", choice
st_low = rules.GameState(max_hp=3698, max_energy=3748)
cs_low = rules.CombatState(our_hp=500, our_energy=3748, attack_links=["Бить"],
                           abilities=[], flee_links=["Сбежать"])
choice = policy.choose(cs_low, st_low, st_low)
assert choice.action == "flee", choice
cs_no_flee = rules.CombatState(our_hp=500, our_energy=3748, attack_links=["Бить"], abilities=[])
choice = policy.choose(cs_no_flee, st_low, st_low)
assert choice.action == "attack", choice
print("CombatPolicy: ok")

# --- LLM: разбор JSON-ответа --------------------------------------
assert ClaudeAdvisor._parse('{"index": 2, "reason": "ok"}')["index"] == 2
assert ClaudeAdvisor._parse("бла-бла { не json") is None
print("llm parse: ok")

print("\nВсе проверки прошли.")
