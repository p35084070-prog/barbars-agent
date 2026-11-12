"""Правила поведения агента: что делать дальше и как вести бой.

Правила детерминированные и дешёвые. Неоднозначные развилки (какую цель бить,
какой талант качать) выносятся к LLM-советнику (llm.py).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import pages
from .driver import CombatState, Game, Status


@dataclass
class Decision:
    """Что агент собирается сделать сейчас."""

    action: str  # fight | repair | talent | quest | donate | wait | explore
    target: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class GameState:
    now: str = ""
    hp: int | None = None
    max_hp: int | None = None
    energy: int | None = None
    max_energy: int | None = None
    level: int | None = None
    xp_cur: int | None = None
    xp_need: int | None = None
    participation: int | None = None
    klass: str = ""
    profession: str = ""
    gold: int | None = None
    silver: int | None = None
    iron: int | None = None
    mifril: int | None = None
    bottles: int | None = None
    talent_points: int = 0
    needs_repair: bool = False
    repair_cost: int | None = None
    altar_bonus: float | None = None
    altar_expires_in_min: float | None = None
    altar_options: list[dict[str, Any]] = field(default_factory=list)
    free_dungeon: int = 0
    free_duel: int = 0
    targets: list[pages.FightTarget] = field(default_factory=list)
    quests: list[pages.ClanQuest] = field(default_factory=list)
    active_quest: str = ""
    # торговля
    market_prices: dict[str, float] = field(default_factory=dict)  # серебро за единицу
    market_checked: bool = False
    my_lots: list[dict[str, Any]] = field(default_factory=list)
    sold_today: int = 0
    # опыт у мудреца
    exp_options: list[dict[str, Any]] = field(default_factory=list)
    exp_buys_today: int = 0
    # колодец удачи
    well_gift_available: bool = False
    well_gift_taken_today: bool = False
    # авторазбор
    autocrack_set_today: bool = False
    autocrack_kind: str = ""
    # рюкзак: шаг «рюкзак» не дал эффекта (сундук полон, надеть нечего)
    gear_blocked: bool = False
    # прокачка: варианты улучшения параметров героя (железо) и мастерства
    master_options: list[dict[str, Any]] = field(default_factory=list)
    mastery_cost: dict[str, int] = field(default_factory=dict)
    # магазин снаряжения: слоты, которые уже куплены (по дневному счётчику)
    shop_slots: list[str] = field(default_factory=list)
    # купленные вещи (id) — их нужно передать другому герою
    shop_bought: list[str] = field(default_factory=list)
    # почта: есть ли что забрать
    mail_pending: bool = False
    # рюкзак и сундук: сколько занято
    bag: dict[str, int] = field(default_factory=dict)
    # содержимое рюкзака (для продажи дублей) и надетое снаряжение
    bag_items: list[dict[str, Any]] = field(default_factory=list)
    worn: list[dict[str, str]] = field(default_factory=list)
    # дубли мифических вещей (слот занят надетой) — их продаём
    duplicates: list[dict[str, Any]] = field(default_factory=list)
    # поля сражений: состояние режима (когда бой, сколько очков) и очки полей
    battlefields: dict[str, Any] = field(default_factory=dict)
    bg_points: int = 0
    # зал кланового босса: HP босса, кто в зале, открыт ли вход
    raid: dict[str, Any] = field(default_factory=dict)
    # когда последний раз ходили в рейд и сколько боссов убили сегодня
    raid_last_at: float = 0.0
    raid_today: int = 0
    # свитки и книги, которые можно активировать
    scrolls: list[dict[str, str]] = field(default_factory=list)
    # слоты нужного героя, которые ещё не закрыты (для покупки на рынке)
    market_due: bool = False
    target_gear: list[dict[str, str]] = field(default_factory=list)
    # аукцион вещей: сколько лотов выставили сегодня
    auction_today: int = 0
    # рынок аукционов: сколько лотов купили сегодня
    market_today: int = 0
    # фарм-события: какие из них сейчас не запускаются (кулдаун)
    farm_skip: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"ур={self.level} класс={self.klass or '?'} hp={self.hp}/{self.max_hp} "
            f"энергия={self.energy}/{self.max_energy} "
            f"золото={self.gold} серебро={self.silver} железо={self.iron} "
            f"мифрил={self.mifril} бутылки={self.bottles} "
            f"опыт={pages.fmt_amount(self.xp_cur)}/{pages.fmt_amount(self.xp_need)} "
            f"участие={pages.fmt_amount(self.participation)} "
            f"свободных_очков_талантов={self.talent_points} "
            f"бесплатных_боёв=подземелья:{self.free_dungeon}/дуэли:{self.free_duel}"
        )


# --------------------------------------------------------------------- сбор состояния


def collect_state(game: Game, config: dict[str, Any]) -> GameState:
    state = GameState()
    # 1. Главная: список доступных боёв + текущие здоровье/энергия.
    game.goto("https://barbars.ru/")
    st = game.status()
    state.hp, state.energy = st.hp, st.energy
    state.targets = pages.home_targets(game)
    for t in state.targets:
        if t.kind in {"dungeon", "tower"} and t.fights_left is not None:
            state.free_dungeon = max(state.free_dungeon, t.fights_left)
        if t.kind == "duel" and t.fights_left is not None:
            state.free_duel = max(state.free_duel, t.fights_left)
    if not state.targets:
        limits = game.fight_limits()
        state.free_dungeon = limits.get("dungeon", state.free_dungeon)
        state.free_duel = limits.get("duel", state.free_duel)

    # 1b. Рюкзак: сколько занято (нужно, чтобы знать, что дроп не влезает).
    if config.get("gear", {}).get("enabled"):
        try:
            state.bag = game.bag_counts()
        except Exception:
            state.bag = {}

    # 1c. Содержимое рюкзака и надетое — нужно для продажи дублей и закупки.
    if config.get("auction", {}).get("enabled") or config.get("shop", {}).get("enabled"):
        try:
            state.worn = game.worn_gear()
            state.bag_items = game.bag_items()
        except Exception:
            state.worn, state.bag_items = [], []

    # 2. Страница героя: статы, опыт, ресурсы, таланты, id героя и клана.
    game.goto("https://barbars.ru/user")
    st = game.status()
    state.hp = state.hp if state.hp is not None else st.hp
    state.energy = state.energy if state.energy is not None else st.energy
    state.gold, state.silver = st.gold, st.silver
    state.iron, state.mifril, state.bottles = st.iron, st.mifril, st.bottles

    hero = game.hero()
    state.level = hero.level
    state.klass = hero.klass or ""
    state.xp_cur, state.xp_need = hero.xp_cur, hero.xp_need
    state.participation = hero.participation
    state.profession = hero.profession or ""
    state.max_hp = state.hp or hero.max_hp
    state.max_energy = hero.max_energy or state.energy

    # 3. Свободные очки талантов — на странице талантов.
    game.goto("https://barbars.ru/user/stances")
    state.talent_points = game.talent_points()

    # 4. Снаряжение: есть ли что чинить и сколько это стоит железа.
    if game.hero_id:
        game.goto(f"https://barbars.ru/user/body/id/{game.hero_id}")
        repair = pages.repair_info(game)
        state.needs_repair = bool(repair.get("needed"))
        state.repair_cost = repair.get("cost")

    # 5. Клановые задания.
    if game.guild_id:
        game.goto(f"https://barbars.ru/guild/quests/0/{game.guild_id}")
        state.active_quest = pages.active_clan_quest(game)
        state.quests = pages.clan_quests(game)
    return state


# --------------------------------------------------------------------- выбор действия


def decide(state: GameState, config: dict[str, Any]) -> Decision:
    """Главный цикл: чини → качай таланты → бери задание → бейся → жертвуй → жди."""
    spend = config.get("spend", {})
    fight_cfg = config.get("fight", {})

    # 1. Починка снаряжения — железо тратится только на ремонт, это всегда полезно.
    if fight_cfg.get("repair_enabled", True) and state.needs_repair:
        cost = state.repair_cost
        if cost is None or (state.iron or 0) >= cost:
            return Decision("repair", reason=f"чиним снаряжение (железа нужно {cost})")

    # 2. Алтарь клана: пожертвование даёт бонус ко всем параметрам клана.
    #    Бонус протухает примерно через 2,5 часа, и он ЗАМЕНЯЕТСЯ новым:
    #    жертвовать вариантом с меньшим бонусом, чем уже есть, нельзя.
    altar_cfg = config.get("altar", {})
    if altar_cfg.get("enabled", True):
        renew_before = float(altar_cfg.get("renew_before_min", 25))
        current_bonus = float(state.altar_bonus or 0)
        expired = current_bonus <= 0
        nearly_over = (
            state.altar_expires_in_min is not None and state.altar_expires_in_min <= renew_before
        )
        if expired or nearly_over:
            # По решению игрока алтарь продлевается ТОЛЬКО железом:
            # серебро и золото на алтарь не тратим.
            allowed = {"iron"}
            if altar_cfg.get("allow_silver", False):
                allowed.add("silver")
            candidates = [o for o in state.altar_options if o.get("kind") in allowed]
            # не понижаем бонус: идём от лучшего бонуса к худшему, но только среди доступных
            candidates.sort(key=lambda o: (o.get("bonus") or 0, -int(o.get("cost") or 0)), reverse=True)
            for best in candidates:
                best_bonus = float(best.get("bonus") or 0)
                # бонус протух — продлеваем любой доступный вариант;
                # если ещё жив — продлеваем только не меньшим бонусом
                if not (expired or best_bonus >= current_bonus):
                    continue
                kind = best.get("kind")
                if kind == "iron":
                    keep = int(altar_cfg.get("keep_iron", 50_000))
                    need = int(best.get("cost") or altar_cfg.get("amount", 1250))
                    if (state.iron or 0) - keep >= need:
                        return Decision(
                            "altar",
                            target="iron",
                            params={"amount": need},
                            reason=f"пожертвуем {need} железа в алтарь (бонус +{best_bonus}%)",
                        )
                elif kind == "silver":
                    # «Пожертвовать 87» — это серебро, а не золото (золото не тратим)
                    need = int(best.get("cost") or 87)
                    keep_silver = int(altar_cfg.get("keep_silver", 20))
                    if (state.silver or 0) - need >= keep_silver:
                        return Decision(
                            "altar",
                            target="silver",
                            params={"amount": need},
                            reason=f"пожертвуем {need} серебра в алтарь (бонус +{best_bonus}%)",
                        )

    # 3. Бесплатный ежедневный подарок колодца удачи.
    well_cfg = config.get("well", {})
    if well_cfg.get("gift_enabled", True) and state.well_gift_available and not state.well_gift_taken_today:
        return Decision("well_gift", reason="забираем бесплатный ежедневный подарок колодца удачи")

    # 4. Свободные очки талантов.
    if state.talent_points > 0:
        return Decision("talent", reason=f"не потрачено очков талантов: {state.talent_points}")

    # 5. Клановое задание — если активного нет, берём подходящее.
    if not state.active_quest and state.quests:
        wanted = _pick_quest(state)
        return Decision("quest", target=wanted, params={"index": wanted.index}, reason="берём клановое задание")

    # 5a. Поля сражений: режим открыт по расписанию, очки за него нужны для
    #     умений, поэтому бойёмся сразу, как только он открылся.
    battlefields = _pick_battlefields(state, config)
    if battlefields is not None:
        return battlefields

    # 5b. Рейд на кланового босса (мифический дракон): общий бой на 10 героев,
    #     поэтому собираемся вместе и бьём, когда пещера открыта.
    raid = _pick_raid(state, config)
    if raid is not None:
        return raid

    # 6. Бой — если есть бесплатные бои и герой не на нуле.
    target = _pick_target(state, config)
    if target is not None:
        return Decision("fight", target=target.title, params={"href": target.href}, reason="используем бесплатный бой")
    if spend.get("allow_gold_fights") and target is None:
        paid = [t for t in state.targets if t.kind in {"dungeon", "duel"}]
        if paid:
            return Decision(
                "fight",
                target=paid[0].title,
                params={"href": paid[0].href, "paid": True},
                reason="платный бой за золото разрешён",
            )

    # 7. Опыт у мудреца — платим железом (золото не трогаем).
    exp_cfg = config.get("exp", {})
    if exp_cfg.get("enabled", True) and state.exp_buys_today < int(exp_cfg.get("max_per_day", 1)):
        keep_iron = int(exp_cfg.get("keep_iron", 100_000))
        free_iron = (state.iron or 0) - keep_iron
        options = [
            o
            for o in state.exp_options
            if o.get("currency") == "iron"
            and o.get("amount", 0) <= free_iron
            and o.get("amount", 0) >= int(exp_cfg.get("min_iron", 5000))
        ]
        if options:
            # выгоднее брать максимум процента за железо
            best = max(options, key=lambda o: o.get("percent", 0))
            return Decision(
                "exp",
                target=str(best["amount"]),
                params={"amount": best["amount"], "percent": best.get("percent")},
                reason=f"покупаем {best.get('percent')}% опыта у мудреца за {best['amount']} железа",
            )

    # 8. Продажа ресурсов на аукционе: мифрил и бутылочки (железо не продаём).
    cancel = _pick_cancel(state, config)
    if cancel is not None:
        return cancel
    sell = _pick_sale(state, config)
    if sell is not None:
        return sell

    # 8.5. Почта: забрать присланные вещи/деньги и надеть их.
    #     Важно раньше шага «рюкзак», чтобы присланное не ушло под разбор.
    if config.get("mail", {}).get("enabled", True) and state.mail_pending:
        return Decision("mail", target="почта", reason="на почте есть что забрать")

    # 8.6. Свитки: активируем бесплатные (при премиуме цена 0) и читаем книги.
    scrolls = _pick_scrolls(state, config)
    if scrolls is not None:
        return scrolls

    # 8.7. Умения за очки полей — копим их на Полях сражений.
    ability = _pick_ability(state, config)
    if ability is not None:
        return ability

    # 9. Рюкзак: надеть лучшие вещи и разобрать остальное на железо.
    #    Забитый рюкзак блокирует новый дроп — из-за этого встаёт опыт.
    gear = _pick_gear(state, config)
    if gear is not None:
        return gear

    # 9a. Прокачка параметров героя железом (/user/master).
    #     Золото по правилам не тратим, поэтому берём только железные варианты.
    upgrade = _pick_upgrade(state, config)
    if upgrade is not None:
        return upgrade

    # 9b. Магазин снаряжения: покупаем вещи 25 уровня (мифические) с
    #     максимальными характеристиками, не дороже лимита по золоту.
    shop = _pick_shop(state, config)
    if shop is not None:
        return shop

    # 9c. Передача золота/серебра другому герою (по заданию игрока).
    share = _pick_share_money(state, config)
    if share is not None:
        return share

    # 9d. Передача купленного снаряжения другому герою (через витрину и почту).
    share_gear = _pick_share_gear(state, config)
    if share_gear is not None:
        return share_gear

    # 9e. Дубли мифических вещей — на аукцион (или отправить тому, кто торгует).
    auction = _pick_auction(state, config)
    if auction is not None:
        return auction

    # 9f. Рынок аукционов вещей: дешёвые мифические вещи нужного уровня.
    market = _pick_trade_market(state, config)
    if market is not None:
        return market

    # 9g. Фарм-события: арена, турниры, выживание, подземелья, великие битвы,
    #     замки. По требованию игрока герой должен быть ПОСТОЯННО в бою, поэтому
    #     события идут выше башен: сначала обязательные события, башни — фоном.
    farm = _pick_farm(state, config)
    if farm is not None:
        return farm

    # 10. Фарм башни: бесплатные бои, капает опыт, железо, бутылочки и вещи.
    #     Это постоянный фон: если события недоступны — герой идёт на башни.
    tower = _pick_tower(state, config)
    if tower is not None:
        return tower

    # 10. Авторазбор вещей в железо/мифрил.
    crack_cfg = config.get("autocrack", {})
    if crack_cfg.get("enabled") and not state.autocrack_set_today:
        kind = crack_cfg.get("kind", "autoCrackCommonLink")
        return Decision("autocrack", target=kind, reason="включаем авторазбор вещей")

    # 11. Вклад в хранилище клана — только излишки железа, и только если разрешено.
    donate_cfg = spend.get("clan_donate", {})
    if donate_cfg.get("enabled") and donate_cfg.get("iron"):
        chunk = int(donate_cfg.get("iron_amount", 50_000))
        keep = int(donate_cfg.get("keep_iron", 500_000))
        if (state.iron or 0) - keep >= chunk:
            return Decision("donate", target="iron", params={"amount": chunk}, reason="вкладываем излишки железа в клан")

    # 13. Ничего не делаем — ждём регенерации/обновления лимитов.
    no_fights = state.free_dungeon <= 0 and state.free_duel <= 0
    return Decision(
        "wait",
        params={"long": no_fights},
        reason="дневные бои исчерпаны, ждём обновления лимитов" if no_fights else "нет доступных действий, ждём регенерации энергии",
    )


def _pick_farm(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Выбрать фарм-событие: любая активность, где можно качать опыт и ресурсы.

    Пропускаем события, которые недавно не удалось запустить (кулдаун),
    и не тратим на них ни золота, ни участия.
    """
    farm_cfg = config.get("farm", {})
    if not farm_cfg.get("enabled", True):
        return None
    skip = set(state.farm_skip or [])
    for event in farm_cfg.get("events", []):
        name = event.get("name", "")
        url = event.get("url", "")
        if not url or name in skip:
            continue
        return Decision(
            "activity",
            target=name,
            params={"url": url, "wait_sec": int(farm_cfg.get("wait_sec", 120))},
            reason=f"фармим событие: {name}",
        )
    return None


def _pick_gear(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Рюкзак: надеть лучшее, остальное разобрать на железо.

    Включается флагом `gear.enabled`. По правилу игрока всё, что можно,
    превращается в железо: сначала надеваем вещи с пометкой «Лучше (+N)»
    (они сильнее надетых), затем ломаем остальное (`gear.crack`).
    Если рюкзак и сундук полны, включает более агрессивный авторазбор
    (`gear.overflow_crack`), чтобы дропы превращались в железо, а не копились.
    """
    cfg = config.get("gear", {})
    if not cfg.get("enabled"):
        return None
    bag = state.bag or {}
    used = int(bag.get("bag_used", 0) or 0)
    total = int(bag.get("bag_total", 20) or 20)
    chest_used = int(bag.get("chest_used", 0) or 0)
    chest_total = int(bag.get("chest_total", 20) or 20)
    keep = int(cfg.get("keep_bag", 4))
    crack_chest = bool(cfg.get("crack_chest", True))
    chest_used = int(bag.get("chest_used", 0) or 0)
    # чистим сундук всегда, если там что-то есть: там копится старый хлам,
    # из-за которого потом некуда складывать новый дроп
    if used <= keep and not (crack_chest and chest_used > 0):
        return None
    overflow = (used >= total) and (chest_used >= chest_total)
    crack = bool(cfg.get("crack", True))
    if overflow and not crack:
        # Разбор на железо выключен: сундук полон, дропы разбираем авторазбором.
        kind = str(cfg.get("overflow_crack", "autoCrackUncommonLink"))
        if state.autocrack_kind != kind:
            return Decision(
                "autocrack",
                target=kind,
                reason="рюкзак и сундук полны — включаем разбор добычи",
            )
        return None
    # Уже пробовали разгрузить рюкзак и не вышло — ждём новый дроп (пауза в цикле).
    if state.gear_blocked:
        return None
    return Decision(
        "gear",
        target="рюкзак",
        params={
            "keep_bag": keep,
            "max_equip": int(cfg.get("max_equip", 8)),
            "crack": crack,
            "sell_store": bool(cfg.get("sell_store", True)),
        },
        reason=f"рюкзак заполнен на {used}/{total} — надеваем лучшее и разбираем остальное",
    )


def _pick_share_gear(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Передать купленное снаряжение другому герою.

    Вещи, купленные в магазине снаряжения, лежат в рюкзаке — их нужно
    отправить получателю (через витрину и почту).
    """
    cfg = config.get("shop", {})
    recipient = str(cfg.get("share_with", "") or "")
    if not recipient:
        return None
    bought = state.shop_bought
    if not bought:
        return None
    return Decision(
        "share_gear",
        target=recipient,
        params={"items": list(bought)},
        reason=f"передаём купленное снаряжение ({len(bought)} шт.) получателю {recipient}",
    )


def _pick_share_money(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Передать золото/серебро другому герою (письмом).

    Задание игрока: золото с firewhite перекладывается на keis, который
    закупает снаряжение и передаёт его обратно.
    """
    cfg = config.get("shop", {})
    recipient = str(cfg.get("share_money_with", "") or "")
    if not recipient:
        return None
    keep_gold = int(cfg.get("keep_gold", 10))
    keep_silver = int(cfg.get("keep_silver", 20))
    gold = int(state.gold or 0) - keep_gold
    silver = int(state.silver or 0) - keep_silver
    if gold <= 0 and silver <= 0:
        return None
    return Decision(
        "share_money",
        target=recipient,
        params={"gold": max(0, gold), "silver": max(0, silver)},
        reason=(
            f"передаём другому герою {max(0, gold)} золота и {max(0, silver)} серебра"
        ),
    )


def _pick_shop(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Закупка снаряжения 25+ уровня в «Магазине снаряжения».

    По правилу игрока: на вещь можно потратить до трёх золотых, берём то,
    что даёт максимальные характеристики («Лучше (+N)»).
    """
    cfg = config.get("shop", {})
    if not cfg.get("enabled"):
        return None
    min_level = int(cfg.get("min_level", 25))
    if int(state.level or 0) < min_level:
        return None
    slots = int(cfg.get("max_slots", 12))
    if int(state.gold or 0) <= 0 and int(state.silver or 0) <= 0:
        return None
    return Decision(
        "shop",
        target="снаряжение",
        params={
            "max_gold": int(cfg.get("max_gold", 3)),
            "max_silver": int(cfg.get("max_silver", 0)),
            "sets": list(cfg.get("sets", ["", "goliaf", "atlant", "veteran"])),
            "max_buys": int(cfg.get("max_buys_per_cycle", 2)),
            "min_bonus": int(cfg.get("min_bonus", 10)),
            "avoid_same_name": bool(cfg.get("avoid_same_name", True)),
        },
        reason=(
            f"покупаем снаряжение {min_level} уровня (куплено слотов: "
            f"{len(state.shop_slots)}/{slots})"
        ),
    )


def _pick_upgrade(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Прокачка параметров героя железом (/user/master).

    Правило игрока: железо тратится на прокачку. Золото по правилам не
    тратим, поэтому варианты за золото пропускаем.
    """
    cfg = config.get("upgrade", {})
    if not cfg.get("enabled"):
        return None
    keep_iron = int(cfg.get("keep_iron", 0))
    iron = int(state.iron or 0)

    # Сначала уровень мастерства: он даёт общий бонус ко всему (+N%).
    # Стоит 35K железа + 200 мифрила (только у героев с открытым мастерством).
    if cfg.get("mastery", False):
        mcost = state.mastery_cost or {}
        need_iron = int(mcost.get("iron", 0))
        need_mifril = int(mcost.get("mifril", 0))
        keep_mifril = int(cfg.get("keep_mifril", 0))
        if need_iron and iron - need_iron >= keep_iron:
            if int(state.mifril or 0) - need_mifril >= keep_mifril:
                return Decision(
                    "upgrade_mastery",
                    target="мастерство",
                    params={"iron": need_iron, "mifril": need_mifril},
                    reason=(
                        f"повышаем уровень мастерства за {need_iron} железа "
                        f"и {need_mifril} мифрила"
                    ),
                )

    if iron <= keep_iron:
        return None
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    for option in state.master_options:
        if option.get("currency") != "iron":
            continue
        cost = int(option.get("cost", 0))
        if cost <= 0 or iron - cost < keep_iron:
            continue
        gain = max(1, int(option.get("gain", 1)))
        ratio = gain / cost
        if best is None or ratio > best_ratio:
            best, best_ratio = option, ratio
    if best is None:
        return None
    return Decision(
        "upgrade",
        target=str(best.get("param", "")),
        params={
            "href": str(best.get("href", "")),
            "cost": int(best.get("cost", 0)),
            "gain": int(best.get("gain", 1)),
        },
        reason=(
            f"качаем параметр {best.get('param')} "
            f"(+{best.get('gain', 1)}) за {best.get('cost')} железа"
        ),
    )


def _pick_auction(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Дубли мифических вещей — на «Аукцион вещей».

    Дубль — вещь, слот которой уже занят надетой. Такие вещи не нужны герою,
    но их нельзя разобрать (мифические), поэтому продаём их лотом.
    Если в конфиге задан `auction.send_to`, вещи не выставляются, а отправляются
    тому герою, у которого доступ к аукциону (у новичка его нет).
    """
    cfg = config.get("auction", {})
    if not cfg.get("enabled"):
        return None
    max_per_day = int(cfg.get("max_per_day", 10))
    if int(state.auction_today or 0) >= max_per_day:
        return None
    if not state.duplicates:
        return None
    max_per_cycle = int(cfg.get("max_per_cycle", 2))
    send_to = str(cfg.get("send_to", "") or "")
    return Decision(
        "auction",
        target="аукцион вещей",
        params={
            "max_per_cycle": max_per_cycle,
            "bid_gold": int(cfg.get("bid_gold", 1)),
            "bid_silver": int(cfg.get("bid_silver", 0)),
            "buyout_gold": int(cfg.get("buyout_gold", 2)),
            "buyout_silver": int(cfg.get("buyout_silver", 0)),
            "send_to": send_to,
            "min_level": int(cfg.get("min_level", 25)),
        },
        reason=(
            "дубли мифических вещей — "
            + (f"отправляем герою {send_to}" if send_to else "выставляем на аукцион")
        ),
    )


def _pick_trade_market(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Рынок аукционов вещей (/trade/auction): покупаем нужному герою.

    На рынке 25-уровневые мифические вещи иногда стоят серебра, а не золота,
    поэтому берём их там и передаём нужному герою.
    """
    cfg = config.get("trade_market", {})
    if not cfg.get("enabled"):
        return None
    if int(state.market_today or 0) >= int(cfg.get("max_per_day", 3)):
        return None
    if not state.market_due:
        return None
    if not (state.gold or 0) and not (state.silver or 0):
        return None
    return Decision(
        "trade_market",
        target="аукцион вещей",
        params={
            "max_gold": int(cfg.get("max_gold", 3)),
            "max_buys": int(cfg.get("max_buys_per_cycle", 1)),
            "min_level": int(cfg.get("min_level", 25)),
            "require_tier": str(cfg.get("require_tier", "мифический")),
            "for_hero": str(cfg.get("for_hero", "") or ""),
            "send_to": str(cfg.get("send_to", "") or ""),
        },
        reason=(
            "покупаем на рынке аукционов "
            + (f"вещи для героя {cfg.get('for_hero')}" if cfg.get("for_hero") else "нужные вещи")
        ),
    )


def _pick_battlefields(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Поля сражений (/game/bg) — командный бой, за который дают очки полей.

    На них покупаются боевые умения, поэтому режим важный, но он открыт
    по расписанию: пока обратный отсчёт, ждём.
    """
    cfg = config.get("battlefields", {})
    if not cfg.get("enabled"):
        return None
    info = state.battlefields or {}
    if not info:
        return None
    countdown = str(info.get("countdown", "") or "")
    join = info.get("join") or []
    if countdown and countdown not in ("00:00:00", "0:00:00") and not join:
        return None  # бой ещё не начался
    if int(info.get("fights_today", 0) or 0) >= int(cfg.get("max_fights_per_day", 5)):
        return None
    return Decision(
        "battlefields",
        target="Поля сражений",
        params={"url": "https://barbars.ru/game/bg"},
        reason=(
            "идём на Поля сражений (очки полей: "
            f"{state.bg_points or info.get('points', 0)})"
        ),
    )


def _pick_raid(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Рейд на кланового босса (Мифический дракон).

    Бой общий: в зале может стоять до 10 героев, дракон один на всех, поэтому
    важно собраться вместе. Пока вход закрыт (бой идёт или откат) — ждём.
    В зал заходим не каждый цикл, а раз в `interval_min`, иначе рейд съест
    всё время и герой не будет качаться.
    """
    cfg = config.get("raid", {}) or {}
    if not cfg.get("enabled"):
        return None
    info = state.raid or {}
    if not info:
        return None
    interval = int(cfg.get("repeat_min", 30)) * 60
    if state.raid_last_at and (time.time() - state.raid_last_at) < interval:
        return None
    if int(state.raid_today or 0) >= int(cfg.get("max_fights_per_day", 10)):
        return None
    url = str(cfg.get("url", "https://barbars.ru/game/dragonDungeon"))
    ready = len(info.get("ready") or [])
    waiting = len(info.get("waiting") or [])
    return Decision(
        "raid",
        target=str(cfg.get("name", "Мифический дракон")),
        params={
            "url": url,
            "min_party": int(cfg.get("min_party", 2)),
            "stay_sec": int(cfg.get("stay_sec", 600)),
            "can_start": bool(cfg.get("can_start", True)),
            "room_check_sec": int(cfg.get("room_check_sec", 8)),
        },
        reason=(
            f"рейд на босса: HP {info.get('hp', 100)}%, в зале {ready + waiting} "
            f"(готовых {ready}), ждём отряд"
        ),
    )


def _pick_ability(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Покупка боевых умений за очки полей (/trade/ability → «За очки полей»)."""
    cfg = config.get("ability", {})
    if not cfg.get("enabled"):
        return None
    points = int(state.bg_points or 0)
    if points <= 0:
        return None
    min_price = int(cfg.get("min_price", 100))
    if points < min_price:
        return None
    return Decision(
        "ability",
        target="умения за очки полей",
        params={
            "prefer": list(cfg.get("prefer", [])),
            "max_price": int(cfg.get("max_price", points)),
            "min_price": min_price,
        },
        reason=f"покупаем умение за очки полей (накоплено {points})",
    )


def _pick_scrolls(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Активация свитков (бесплатно при премиуме) и чтение книг."""
    cfg = config.get("scrolls", {})
    if not cfg.get("enabled"):
        return None
    if not state.scrolls:
        return None
    return Decision(
        "scrolls",
        target="свитки",
        params={"only_free": bool(cfg.get("only_free", True)), "limit": int(cfg.get("limit", 5))},
        reason=f"активируем свитки: {len(state.scrolls)} шт.",
    )


def _pick_tower(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Фарм башни (/game/towers) — бесплатный бой с добычей опыта и ресурсов.

    Включается флагом `tower_farm.enabled`. Опционально `tower_farm.max_level`:
    выше этого уровня башня больше не фармится (0 — без ограничения).
    """
    cfg = config.get("tower_farm", {})
    if not cfg.get("enabled"):
        return None
    max_level = int(cfg.get("max_level", 0) or 0)
    if max_level and (state.level or 0) > max_level:
        return None
    return Decision(
        "tower",
        target="башня",
        params={"rounds": int(cfg.get("rounds", 3))},
        reason="фармим башню: опыт, железо, бутылочки и вещи",
    )


def _pick_cancel(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Снять свой лот, если рынок просел ниже цены лота.

    Лот висит 24 часа и стоит 5 серебра аренды; если за это время рынок упал,
    лучше снять лот и выставить его позже по новой цене.
    """
    market = config.get("market", {})
    if not market.get("enabled", True):
        return None
    drift = float(market.get("cancel_drift_ratio", 1.2))
    for lot in state.my_lots:
        resource = lot.get("resource", "")
        unit = state.market_prices.get(resource)
        if not unit:
            continue
        lot_unit = lot.get("unit_price_silver", 0.0)
        if lot_unit > unit * drift:
            return Decision(
                "cancel_lot",
                target=resource,
                params={"unit_price": lot_unit},
                reason=(
                    f"снимаем лот {resource}: цена {lot_unit:.2f} сер/шт выше рынка {unit:.2f}"
                ),
            )
    return None


def _pick_sale(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Какой ресурс и по какой цене выставить на аукционе ресурсов.

    Продаём только мифрил и бутылочки (железо нужно на починку/алтарь/опыт).
    Цену берём лучшую рыночную за единицу и слегка снижаем, чтобы лот ушёл быстрее.
    Лот стоит 5 серебра за 24 часа — выставляем только если выручка заметно больше.
    """
    market = config.get("market", {})
    if not market.get("enabled", True):
        return None
    if state.sold_today >= int(market.get("max_lots_per_day", 2)):
        return None
    reserves = market.get("reserve", {})
    min_amount = market.get("min_amount", {})
    min_price = market.get("min_unit_price", {})
    min_revenue = int(market.get("min_revenue_silver", 500))

    have_map = {"mifril": state.mifril or 0, "bottles": state.bottles or 0}
    # если по этому ресурсу уже висит наш лот — второй не выставляем
    busy = {lot.get("resource") for lot in state.my_lots}
    for resource in market.get("resources", ["mifril", "bottles"]):
        if resource in busy:
            continue
        have = have_map.get(resource, 0)
        reserve = int(reserves.get(resource, 0))
        surplus = have - reserve
        if surplus < int(min_amount.get(resource, 1000)):
            continue
        unit = state.market_prices.get(resource)
        if not unit:
            continue
        if unit < float(min_price.get(resource, 0.0)):
            continue
        # цена за единицу: чуть ниже лучшей рыночной, с ограничением снизу
        price_per_unit = unit - float(market.get("price_discount", 0.01))
        price_per_unit = max(price_per_unit, float(min_price.get(resource, 0.0)))
        total = int(price_per_unit * surplus)
        if total < min_revenue:
            continue
        gold, silver = divmod(total, 100)
        if gold <= 0 and silver <= 0:
            continue
        return Decision(
            "sell",
            target=resource,
            params={"amount": surplus, "gold": gold, "silver": silver, "unit_price": price_per_unit},
            reason=(
                f"продаём {surplus} {resource} по {price_per_unit:.3f} сер/шт "
                f"(выручка {gold}з {silver}с)"
            ),
        )
    return None


def _repair_cost(config: dict[str, Any]) -> int | None:
    return config.get("fight", {}).get("repair_reserve", None)


def _pick_quest(state: GameState) -> pages.ClanQuest:
    """Приоритет: задания, которые мы реально выполняем текущими боями."""
    priority = (
        "Усиленная прокачка",
        "Рейд на драконов",
        "Лицом к лицу",
        "Покорение турниров",
        "Кровавая арена",
        "Выжить любой ценой",
        "Великие свершения",
    )
    for want in priority:
        for q in state.quests:
            if want.lower() in (q.title + " " + q.description).lower():
                return q
    return state.quests[0]


def _pick_target(state: GameState, config: dict[str, Any]) -> pages.FightTarget | None:
    """Какой бой взять: приоритет из конфига, иначе — по типу и остатку попыток."""
    order = config.get("targets", ["dungeon", "tower", "duel", "arena", "survival", "greats", "contests"])
    by_kind: dict[str, list[pages.FightTarget]] = {}
    for t in state.targets:
        by_kind.setdefault(t.kind, []).append(t)
    for kind in order:
        options = by_kind.get(kind) or []
        if not options:
            continue
        # дуэли и подземелья — только если есть бесплатные попытки
        if kind == "duel" and state.free_duel <= 0:
            continue
        if kind == "dungeon" and state.free_dungeon <= 0:
            continue
        if kind == "tower" and state.free_dungeon <= 0:
            continue
        options.sort(key=lambda t: (t.fights_left is None, -(t.fights_left or 0)))
        return options[0]
    return None


# --------------------------------------------------------------------- политика боя


class CombatPolicy:
    """Пошаговая логика внутри боя."""

    def __init__(self, config: dict[str, Any]):
        cfg = config.get("fight", {})
        self.hp_flee = cfg.get("hp_flee_threshold", 30)
        self.potion_below = cfg.get("use_potions_below_hp", 25)
        self.energy_threshold = cfg.get("energy_attack_threshold", 0.85)
        self.max_turns = cfg.get("max_turns", 80)
        self.prefer_heal = cfg.get("prefer_heal", False)

    def choose(self, cs: CombatState, status: Status, state: GameState, force: bool = False) -> Decision:
        """Что нажать в этом ходе."""
        if cs.victory is True:
            return Decision("finish", reason="победа")
        if cs.victory is False:
            return Decision("finish", reason="поражение")

        max_hp = state.max_hp or cs.our_hp or 0
        hp_ratio = (cs.our_hp or 0) / max_hp if max_hp else 1.0

        # Зелье при низком здоровье.
        if cs.potion_links and hp_ratio * 100 < self.potion_below:
            return Decision("potion", params={"text": cs.potion_links[0]}, reason="хилка на низком HP")

        # Умения: сначала «увеличивает урон» перед ударом, затем защита.
        boost = next((a for a in cs.abilities if a["ready"] and "увеличивает урон" in a.get("desc", "")), None)
        shield = next((a for a in cs.abilities if a["ready"] and "уменьшает урон" in a.get("desc", "")), None)
        dodge = next((a for a in cs.abilities if a["ready"] and "уворот" in a.get("desc", "")), None)

        if boost:
            return Decision("ability", target=boost["name"], params={"href": boost["href"]}, reason="буст урона")
        if shield and hp_ratio * 100 < 70:
            return Decision("ability", target=shield["name"], params={"href": shield["href"]}, reason="щит при низком HP")
        if dodge and hp_ratio * 100 < 45:
            return Decision("ability", target=dodge["name"], params={"href": dodge["href"]}, reason="уклонение при низком HP")

        # Критическое здоровье — отступаем, а не продолжаем бить.
        if cs.flee_links and hp_ratio * 100 < self.hp_flee:
            return Decision("flee", params={"text": cs.flee_links[0]}, reason="HP критическое, отступаем")

        # Энергия должна быть почти максимальной: урон растёт с зарядом меча.
        # В бою с боссом окно попытки короткое: лечить (у медика удара нет)
        # надо сразу, а вот удар лучше делать с полным зарядом.
        energy_max = state.max_energy or cs.our_energy or 0
        energy_now = cs.our_energy or 0
        need_energy = not (force and not cs.attack_links)
        if need_energy and energy_max and energy_now < energy_max * self.energy_threshold:
            return Decision("wait_energy", reason=f"ждём энергию {energy_now}/{energy_max}")

        if cs.attack_links:
            return Decision("attack", reason="обычный удар")
        if cs.heal_links:
            # В клановых боях и в осаде башни у медика нет удара — лечение
            # единственное действие, иначе бой простаивает.
            return Decision("heal", params={"text": cs.heal_links[0]}, reason="лечим союзника")
        return Decision("wait", reason="нет доступных действий в бою")
