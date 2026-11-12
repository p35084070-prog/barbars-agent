"""Разбор содержимого ключевых страниц игры: список целей боя, задания клана, таланты."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .driver import Game, normalize_ru, parse_amount


@dataclass
class FightTarget:
    """Доступный бой на главной странице."""

    title: str
    href: str
    kind: str = ""  # dungeon / duel / tower / arena / ...
    fights_left: int | None = None


@dataclass
class ClanQuest:
    title: str
    description: str = ""
    reward_text: str = ""
    index: int = 0


@dataclass
class Talent:
    name: str
    spent: int | None = None
    max_rank: int | None = None
    studied: bool = False
    group: str = ""


def _hrefs(page) -> dict[str, str]:
    out: dict[str, str] = {}
    for link in page.locator("a").all():
        try:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""
        except Exception:
            continue
        if text and href and text not in out:
            out[text] = href
    return out


def home_targets(game: Game) -> list[FightTarget]:
    """Бои, доступные с главной страницы ('Башня призраков осталось 2 боя')."""
    targets: list[FightTarget] = []
    for link in game.p.locator("a").all():
        try:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""
        except Exception:
            continue
        if not text or not href:
            continue
        m = re.search(r"([^\n]*?)\s*остал\w*\s*(\d+)\s*бо", text, re.IGNORECASE)
        if not m:
            continue
        title = m.group(1).strip()
        targets.append(
            FightTarget(
                title=title,
                href=href,
                kind=classify_target(title, href),
                fights_left=int(m.group(2)),
            )
        )
    return targets


def classify_target(title: str, href: str) -> str:
    blob = f"{title} {href}".lower()
    if "владения" in blob or "поля сраж" in blob or "медуз" in blob:
        return "battlefields"
    if "дуэл" in blob or "duel" in blob:
        return "duel"
    if "арен" in blob or "arena" in blob:
        return "arena"
    if "пещер" in blob or "dungeon" in blob or "ogre" in blob or "dragon" in blob:
        return "dungeon"
    if "башн" in blob or "tower" in blob:
        return "tower"
    if "выживан" in blob or "survival" in blob:
        return "survival"
    if "велик" in blob or "great" in blob:
        return "greats"
    if "турнир" in blob or "contest" in blob:
        return "contests"
    if "замк" in blob or "castle" in blob:
        return "castles"
    return "other"


def fightmore_options(game: Game) -> dict[str, Any]:
    """Страница /fightmore: остатки бесплатных боёв и стоимость платного."""
    text = game.body_text()
    info: dict[str, Any] = {"free_dungeon": 0, "free_duel": 0, "paid_fight_cost": None}
    m = re.search(r"провести\s*(\d+)\s*бо(?:я|и|ев)\s*в подземельях\s*и\s*(\d+)\s*бо(?:я|и|ев)\s*в дуэлях", text, re.IGNORECASE)
    if m:
        info["free_dungeon"] = int(m.group(1))
        info["free_duel"] = int(m.group(2))
    m = re.search(r"Сразиться ещё за\s*(\d+)\s*(?:золото|золот)", text, re.IGNORECASE)
    if m:
        info["paid_fight_cost"] = int(m.group(1))
    return info


def dungeon_list(game: Game) -> list[FightTarget]:
    """Список боссов на /game/dungeons."""
    out: list[FightTarget] = []
    for link in game.p.locator("a").all():
        try:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""
        except Exception:
            continue
        if not text or "dungeon" not in href.lower() and not href.startswith("../game/"):
            continue
        if not re.search(r"game/[a-zA-Z]", href):
            continue
        if text.lower() in {"общие", "клановые", "испытания"}:
            continue
        if any(t.title == text for t in out):
            continue
        out.append(FightTarget(title=text, href=href, kind="dungeon"))
    return out


def clan_quests(game: Game) -> list[ClanQuest]:
    """Задания клана на /guild/quests/0/<id>. Активное задание не возвращается."""
    quests: list[ClanQuest] = []
    lines = [line.strip() for line in game.body_text().splitlines()]
    verbs = ("Убей", "Победи", "Выживи", "Заработай")
    title = ""
    index = 0
    for position, line in enumerate(lines):
        if line.startswith(verbs):
            description = line
            reward = ""
            active = False
            for follow in lines[position + 1 : position + 6]:
                if follow.startswith("Награда:"):
                    reward = follow[len("Награда:") :].strip()
                    break
                if follow.startswith("Прогресс:") or follow.startswith("Выполняет:"):
                    active = True
            if not active and title:
                quests.append(
                    ClanQuest(
                        title=title,
                        description=description,
                        reward_text=reward,
                        index=index,
                    )
                )
                index += 1
            title = ""
        elif line and not line.startswith(("Награда:", "Прогресс:", "Выполняет:", "Осталось:", "Подробная", "Клановое")):
            title = line
    return quests


def active_clan_quest(game: Game) -> str:
    """Название уже взятого задания (пусто, если заданий нет)."""
    lines = [line.strip() for line in game.body_text().splitlines()]
    for position, line in enumerate(lines):
        if line.startswith("Прогресс:") or line.startswith("Выполняет:"):
            for back in range(position - 1, -1, -1):
                candidate = lines[back]
                if candidate and not candidate.startswith(("Клановые задания", "Выполни задание")):
                    return candidate
    return ""


def talents(game: Game) -> list[Talent]:
    """Список талантов на /user/stances."""
    out: list[Talent] = []
    for row in game.p.locator("tr").all():
        try:
            text = row.inner_text().strip()
        except Exception:
            continue
        m = re.match(r"^(.+?)\s*\[(\d+)/(\d+)\]", text)
        if not m:
            continue
        name = m.group(1).strip()
        if not name or name in {"Набор"}:
            continue
        out.append(
            Talent(
                name=name,
                spent=int(m.group(2)),
                max_rank=int(m.group(3)),
                studied="изучено" in text.lower(),
            )
        )
    return out


def donate_controls(game: Game) -> list[dict[str, str]]:
    """Найти на странице клана элементы для вклада ресурсов."""
    keys = ("вложить", "положить", "пожертвовать", "внести", "донат", "закинуть", "передать")
    found: list[dict[str, str]] = []
    for tag in ("a", "button", "input"):
        for locator in game.p.locator(tag).all():
            try:
                text = locator.inner_text().strip() or (locator.get_attribute("value") or "")
                href = locator.get_attribute("href") or ""
            except Exception:
                continue
            low = text.lower()
            if any(k in low for k in keys):
                found.append({"text": text, "href": href, "tag": tag})
    return found


def repair_info(game: Game) -> dict[str, Any]:
    """Есть ли что чинить: {'needed': bool, 'cost': int|None, 'text': str}."""
    info: dict[str, Any] = {"needed": False, "cost": None, "text": ""}
    for link in game.p.locator("a, button").all():
        try:
            text = link.inner_text().strip()
        except Exception:
            continue
        if "Починить" not in text:
            continue
        info["needed"] = True
        info["text"] = text
        m = re.search(r"за\s*([\d.,]+)", text)
        if m:
            info["cost"] = parse_amount(m.group(1))
        break
    return info


def altar_info(game: Game) -> dict[str, Any]:
    """Состояние алтаря клана: бонус, остаток его действия и варианты пожертвования.

    Доступные варианты — это ссылки `sacrifice*Link`; пока бонус жив, варианты
    показаны серым текстом (без ссылки) и пожертвовать нельзя.
    Валюта варианта определяется по иконке: ironbar (железо), money_silver (серебро),
    money_gold (золото — его не тратим).
    """
    info: dict[str, Any] = {
        "bonus": None,
        "expires_in_min": None,
        "iron_cost": None,
        "iron_bonus": None,
        "silver_cost": None,
        "silver_bonus": None,
        "options": [],
    }
    text = game.body_text()
    m = re.search(r"Твой бонус:\s*\+([\d.,]+)%", text)
    if m:
        try:
            info["bonus"] = float(m.group(1).replace(",", "."))
        except ValueError:
            info["bonus"] = None
    m = re.search(r"Твой бонус:[^\[]*\[\s*(\d+)\s*ч\.?\s*(\d+)?\s*мин", text)
    if m:
        info["expires_in_min"] = int(m.group(1)) * 60 + int(m.group(2) or 0)
    for link in game.p.locator("a").all():
        try:
            label = (link.inner_text() or "").strip().replace("\n", " ")
            href = link.get_attribute("href") or ""
            outer = link.evaluate("el => el.outerHTML") or ""
        except Exception:
            continue
        if "sacrifice" not in href.lower():
            continue
        bonus = None
        bm = re.search(r"\+([\d.,]+)\s*%", label)
        if bm:
            try:
                bonus = float(bm.group(1).replace(",", "."))
            except ValueError:
                bonus = None
        amount = None
        m2 = re.search(r"Пожертвовать\s*([\d\s]+)", label)
        if m2:
            amount = parse_amount(m2.group(1))
        # валюта определяется по иконкам внутри ссылки
        has_iron = "ironbar" in outer
        has_silver = "money_silver" in outer
        has_gold = "money_gold" in outer
        if has_iron and not has_silver and not has_gold:
            kind = "iron"
            info["iron_cost"] = amount
            info["iron_bonus"] = bonus
        elif has_silver and not has_gold:
            kind = "silver"
            info["silver_cost"] = amount
            info["silver_bonus"] = bonus
        elif has_gold:
            kind = "gold"
        else:
            kind = "other"
        if kind in {"iron", "silver"} and amount:
            info["options"].append({"kind": kind, "cost": amount, "bonus": bonus})
    return info


def storage_text(game: Game) -> str:
    """'Хранилище: 1070500 1635 44' — железо/серебро/мифрил на складе клана."""
    text = game.body_text()
    m = re.search(r"Хранилище:\s*([\d,\s]+)", text)
    if not m:
        return ""
    return m.group(1).strip()


def resources_summary(game: Game) -> str:
    st = game.status()
    return (
        f"золото={st.gold}, серебро={st.silver}, железо={st.iron}, "
        f"мифрил={st.mifril}, бутылки={st.bottles}"
    )


# --------------------------------------------------------------------- торговля

# Иконки ресурсов на аукционе: бутылочки, мифрил, железо.
_RESOURCE_ICONS = {
    "bottles": "bottle",
    "mifril": "mifrilbar",
    "iron": "ironbar",
}

_LOT_RE = re.compile(
    r'<img[^>]*src="/images/icons/(?P<res>bottle|mifrilbar|ironbar)\.png"[^>]*>\s*'
    r"<span>(?P<qty>[\d\s]+)</span>\s*"
    r"<span>(?P<unit>[^<]{1,12})</span>\s*"
    r"<span>(?P<money>.*?)</div>",
    re.S,
)
_GOLD_RE = re.compile(r"money_gold\.png\"[^>]*>\s*<span>([\d\s]+)</span>", re.S)
_SILVER_RE = re.compile(r"money_silver\.png\"[^>]*>\s*<span>([\d\s]+)</span>", re.S)


SLOT_KEYS: list[tuple[str, str]] = [
    ("наплечник", "наплечники"),
    ("медальон", "амулет"),
    ("амулет", "амулет"),
    ("шлем", "шлем"),
    ("накидка", "накидка"),
    ("бурка", "накидка"),
    ("бушлат", "броня"),
    ("кольчуга", "броня"),
    ("кираса", "броня"),
    ("поножи", "штаны"),
    ("штаны", "штаны"),
    ("пояс", "пояс"),
    ("наручи", "перчатки"),
    ("браслет", "браслеты"),
    ("перчатки", "перчатки"),
    ("рукавицы", "перчатки"),
    ("перстень", "кольцо"),
    ("кольцо", "кольцо"),
    ("сапоги", "обувь"),
    ("ботинки", "обувь"),
]

WEAPON_KINDS = ("секира", "топор", "копье", "копьё", "посох", "молот", "меч")


def slot_of(name: str) -> tuple[str, str]:
    """Слот и тип (для оружия) по названию вещи.

    «Шлем Берсерка» -> («шлем», «»), «Секира Воина» -> («оружие», «секира»).
    Пустой слот означает, что название не распознано.
    """
    low = name.lower()
    for kind in WEAPON_KINDS:
        if kind in low:
            return ("оружие", kind)
    for key, slot in SLOT_KEYS:
        if key in low:
            return (slot, "")
    return ("", "")


def parse_worn_gear(html: str) -> list[dict[str, str]]:
    """Что надето на герое (/user/body/id/<id>).

    Вёрстка бывает двух видов:
      * «Шлем Голиафа 25 ур, Шлем» — слот прямо в тексте;
      * «Шлем Ветерана 50 ур, +150 брони» — слота нет, берём из названия.
    Возвращает: [{"name", "slot", "level"}].
    """
    slots = {
        "шлем", "амулет", "наплечники", "накидка", "броня", "пояс",
        "штаны", "браслеты", "перчатки", "кольцо", "оружие", "обувь",
    }
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(
        r"item/id/\d+\"><span>([^<]{2,40})</span></a>.{0,220}?(\d+)(?:</span>)?\s*ур(.{0,80})",
        re.S,
    )
    for m in pattern.finditer(html):
        name = m.group(1).strip()
        tail = re.sub("<[^>]+>", " ", m.group(3) or "").lower()
        slot = ""
        for word in slots:
            if re.search(rf"\b{word}\b", tail):
                slot = word
                break
        if not slot:
            slot = slot_of(name)[0]
        if slot and (name, slot) not in seen:
            seen.add((name, slot))
            out.append({"name": name, "slot": slot, "level": m.group(2).strip()})
    return out


def parse_price_text(text: str) -> tuple[int, int]:
    """(золото, серебро) из текста с ценой.

    Форматы в игре: «Купить за 560» (серебро), «Купить за 6 зол 50 сер»,
    «Выкупить сразу за 23», «Ставка: 1 зол 20 сер», «цена: 65».
    """
    t = " ".join(text.split())
    gold = silver = 0
    m = re.search(r"(\d[\d\s.,]*)\s*(?:золот\w*|зол\.?)", t, re.IGNORECASE)
    if m:
        gold = parse_amount(m.group(1))
    m = re.search(r"(\d[\d\s.,]*)\s*(?:серебр\w*|сер\.?)", t, re.IGNORECASE)
    if m:
        silver = parse_amount(m.group(1))
    if not gold and not silver:
        # «Купить за 560» — число без указания валюты означает серебро
        m = re.search(
            r"(?:Купить за|Выкупить сразу за|цена:?|ставка:?)\s*(\d[\d\s.,]*)",
            t,
            re.IGNORECASE,
        )
        if m:
            silver = parse_amount(m.group(1))
    return gold, silver


def cyr_normalize(text: str) -> str:
    """Привести латинские «двойники» к кириллице.

    Игра маскирует часть букв: «Берсерк» приходит как «Бepcepк» (латинские
    e, p, c, k). Чтобы сравнивать названия, приводим их к одному виду.
    """
    return " ".join(normalize_ru(text).split())


def parse_raid_room(html: str, text: str = "") -> dict[str, Any]:
    """Зал кланового босса (/game/dragonDungeon и подобные).

    Возвращает: {"closed", "reopen_in", "hp", "warriors", "healers", "ready",
    "waiting", "limit", "in_fight", "locked_out", "can_start"}.
    """
    text = text or " ".join(re.sub("<[^>]+>", " ", html).split())
    out: dict[str, Any] = {
        "closed": False,
        "reopen_in": "",
        "hp": 0,
        "warriors": 0,
        "healers": 0,
        "ready": [],
        "waiting": [],
        "limit": 0,
        "in_fight": False,
        "can_start": "startCombatLink" in html,
    }
    m = re.search(r"Откроется через[:\s]*([\d:]+)", text)
    if m:
        out["reopen_in"] = m.group(1)
    out["closed"] = (
        ("Вход закрыт" in text)
        or ("Пустая пещера" in text)
        or ("Бой начался" in text)
    )

    # иконки-параметры: HP босса (%), воины, лекари, часы
    for m in re.finditer(
        r'<img[^>]+src="/images/icons/([\w]+)\.png"[^>]*>\s*<span[^>]*>([^<]*)</span>', html
    ):
        icon, value = m.group(1), m.group(2).strip()
        if value.endswith("%"):
            try:
                out["hp"] = int(value[:-1] or 0)
            except ValueError:
                pass
        elif "warrior" in icon:
            out["warriors"] = int(value or 0) if value.isdigit() else 0
        elif "healer" in icon:
            out["healers"] = int(value or 0) if value.isdigit() else 0

    # кто в зале и кто готов
    idx = html.find("Кто здесь")
    if idx >= 0:
        head = html[idx:idx + 120]
        m = re.search(r"Кто здесь\s*\[(\d+)\s*из\s*(\d+)\]", head)
        if m:
            out["limit"] = int(m.group(2))
        block = html[idx:idx + 4000]
        for chunk in block.split("<div>")[1:]:
            hero = re.search(r'user/id/(\d+)"><span>([^<]+)</span>', chunk)
            if not hero:
                continue
            entry = {"id": hero.group(1), "name": hero.group(2)}
            (out["ready"] if "check_green" in chunk else out["waiting"]).append(entry)

    # Боевую панель во время попытки отдаётся участнику прямо на странице зала:
    # «Бить дракона» (воин) или «Лечить союзников» (медик) + «<кто-то> начал бой».
    # «Покинуть бой» не годится как признак: он есть и на странице отказа
    # («Вход закрыт. Бой начался… ты не можешь принять участие»).
    out["in_fight"] = (
        "Бить дракона" in text
        or "Лечить союзников" in text
        or "начал бой" in text
    )
    out["locked_out"] = "не можешь принять участие" in text
    return out


def parse_battlefields(html: str, text: str = "") -> dict[str, Any]:
    """Состояние «Полей сражений» (/game/bg) — командный бой за очки полей.

    Возвращает: {"countdown", "fights_today", "points", "join", "text"}.
    """
    text = text or " ".join(re.sub("<[^>]+>", " ", html).split())
    countdown = ""
    m = re.search(r"Игра начн[её]тся через[:\s]*([\d:]+)", text, re.IGNORECASE)
    if m:
        countdown = m.group(1)
    fights_today = 0
    m = re.search(r"Сегодня бо[её]в[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        fights_today = int(m.group(1))
    points = 0
    m = re.search(r"Мои очки полей[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        points = int(m.group(1))
    join: list[dict[str, str]] = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
        href = m.group(1)
        low = (label + " " + href).lower()
        if "refresh" in low:
            continue
        if any(
            k in low
            for k in (
                "join", "start", "fight", "battle", "attack",
                "вступи", "начать", "атакова", "в бой", "бой", "штурм",
                "участв", "зайти", "войти",
            )
        ):
            join.append({"label": label, "href": href})
    return {
        "countdown": countdown,
        "fights_today": fights_today,
        "points": points,
        "join": join,
        "text": text[:400],
    }


def parse_ability_options(html: str) -> dict[str, Any]:
    """Опции покупки умения за очки полей (/trade/ability/buy/0/<id>).

    Блок варианта: «<span>Берсерк</span>, <span>легендарный</span> ... [<a
    ...buyBlock:N:bgWinsBuyLink...>купить</a>] цена:<span class="money">500</span>».
    Возвращает: {"points": int, "options": [{"index", "name", "quality", "price"}]}.
    """
    text = " ".join(re.sub("<[^>]+>", " ", html).split())
    points = 0
    m = re.search(r"У тебя очков полей[:\s]*(\d+)", text, re.IGNORECASE)
    if m:
        points = int(m.group(1))
    options: list[dict[str, Any]] = []
    for chunk in html.split('<div class="hr"></div>'):
        m = re.search(r"buyBlock:(\d+):bgWinsBuyLink", chunk)
        if not m:
            continue
        name_m = re.search(r"<span>([^<]{2,40})</span>\s*,\s*<span>([^<]{2,20})</span>", chunk)
        price_m = re.search(r"цена[:\s]*(?:<[^>]+>\s*)*<span[^>]*>([\d\s]+)</span>", chunk)
        if not price_m:
            price_m = re.search(r"цена[:\s]*([\d\s]+)", " ".join(re.sub("<[^>]+>", " ", chunk).split()))
        options.append(
            {
                "index": int(m.group(1)),
                "name": cyr_normalize(name_m.group(1)) if name_m else "",
                "quality": (name_m.group(2) if name_m else ""),
                "price": int(re.sub(r"\D", "", price_m.group(1)) or 0) if price_m else 0,
            }
        )
    return {"points": points, "options": options}


def parse_market_lots(html: str) -> list[dict[str, Any]]:
    """Лоты «Аукциона вещей» (/trade/auction).

    Блок лота: ссылка на страницу лота `trade/auction/item/id/<id>/pt/<pt>`,
    название, уровень, качество и цена (серебро/золото иконками или текстом).
    Возвращает: {"name", "item_id", "pt", "level", "tier", "gold", "silver",
    "price_silver", "href"}.
    """
    out: list[dict[str, Any]] = []
    for chunk in html.split('<div class="hr"></div>'):
        m = re.search(r"trade/auction/item/id/(\d+)/pt/(\d+)", chunk)
        if not m:
            continue
        name_m = re.search(r"item/id/\d+/pt/\d+\"[^>]*>(?:<span>)?([^<]{2,60})", chunk)
        level_m = re.search(r"(\d+)(?:</span>)?\s*ур", chunk)
        tier = "?"
        for key, label in (
            ("bonusdarkiron", "мифический"),
            ("bonuslegendary", "легендарный"),
            ("bonusepic", "эпический"),
            ("bonusrare", "редкий"),
            ("bonusgreen", "необычный"),
            ("bonuscopper", "обычный"),
        ):
            if key in chunk:
                tier = label
                break
        gold = silver = 0
        for icon, number in re.findall(
            r"icons/(money_gold|money_silver)\.png\"[^>]*>\s*<span>([\d.,]+)</span>", chunk
        ):
            value = parse_amount(number)
            if icon == "money_gold":
                gold = value
            else:
                silver = value
        if not gold and not silver:
            text = re.sub("<[^>]+>", " ", chunk)
            price_m = re.search(r"цена\s*:?\s*([^\n]{0,40})", text, re.IGNORECASE)
            if price_m:
                gold, silver = parse_price_text(price_m.group(1))
        out.append(
            {
                "name": name_m.group(1).strip() if name_m else "",
                "item_id": m.group(1),
                "pt": int(m.group(2)),
                "href": f"trade/auction/item/id/{m.group(1)}/pt/{m.group(2)}",
                "level": int(level_m.group(1)) if level_m else 0,
                "tier": tier,
                "gold": gold,
                "silver": silver,
                "price_silver": gold * 100 + silver,
            }
        )
    return out


def parse_shop_gear(html: str) -> list[dict[str, Any]]:
    """Товары «Магазина снаряжения» (/trade/auction/shop).

    Блок товара: картинка, название со ссылкой на страницу товара, уровень,
    пометка «Лучше (+N)» и цена (серебро и/или золото иконками).
    Возвращает: {"name", "level", "bonus", "gold", "silver", "item_id",
    "tier", "href"}.
    """
    out: list[dict[str, Any]] = []
    for chunk in html.split('<div class="hr"></div>'):
        m = re.search(
            r'href="(?:\.\./)*(trade/auction/shop/item/id/(\d+))"><span>([^<]+)</span>', chunk
        )
        if not m:
            continue
        level_m = re.search(r"(\d+)(?:</span>)?\s*ур\b", chunk)
        bonus_m = re.search(r"Лучше\s*\(\s*\+(\d+)\s*\)", chunk)
        tier = "?"
        for key, label in (
            ("bonusdarkiron", "мифический"),
            ("bonuslegendary", "легендарный"),
            ("bonusepic", "эпический"),
            ("bonusrare", "редкий"),
            ("bonusgreen", "необычный"),
            ("bonuscopper", "обычный"),
        ):
            if key in chunk:
                tier = label
                break
        gold = silver = 0
        price_html = chunk
        price_at = chunk.find("цена")
        if price_at > 0:
            price_html = chunk[price_at:price_at + 300]
        for icon, number in re.findall(
            r"icons/(money_gold|money_silver)\.png\"[^>]*>\s*<span>([\d.,]+)</span>", price_html
        ):
            value = parse_amount(number)
            if icon == "money_gold":
                gold = value
            else:
                silver = value
        if not gold and not silver:
            # запасной вариант: цена текстом («Купить за 80», «Купить за 6 зол 50 сер»)
            text = re.sub("<[^>]+>", " ", price_html)
            gold, silver = parse_price_text(text)
        out.append(
            {
                "name": m.group(3).strip(),
                "item_id": m.group(2),
                "href": m.group(1),
                "level": int(level_m.group(1)) if level_m else 0,
                "bonus": int(bonus_m.group(1)) if bonus_m else 0,
                "gold": gold,
                "silver": silver,
                "tier": tier,
                # цена не распознана — покупать вслепую нельзя
                "price_ok": bool(gold or silver),
            }
        )
    return out


def pick_shop_items(
    items: list[dict[str, Any]],
    worn: list[dict[str, str]],
    max_gold: int = 3,
    max_silver: int = 0,
    bought_slots: tuple[str, ...] | list[str] = (),
    require_better: bool = True,
    min_bonus: int = 0,
    avoid_same_name: bool = False,
    min_level: int = 0,
) -> list[dict[str, Any]]:
    """Выбрать товары магазина снаряжения к покупке.

    Правила:
      * золота на вещь — не больше max_gold (серебро — если max_silver задан);
      * оружие берём только того же типа, что надето (иначе герой его не наденет);
      * берём только вещи с бонусом «Лучше (+N)»: в магазине это сравнение с
        надетой вещью, то есть N = 0 означает «дубль, покупать не нужно»;
      * бонус должен быть не меньше min_bonus (мелочь вроде +1 не покупаем);
      * при avoid_same_name не берём вещь, одноимённую с надетой (чистый дубль);
      * на каждый слот — одна вещь, с максимальным бонусом;
      * уже купленные слоты пропускаем.
    """
    weapon_kind = ""
    worn_names: dict[str, str] = {}
    for w in worn:
        if w.get("slot") == "оружие":
            weapon_kind = slot_of(w.get("name", ""))[1]
        slot, _kind = slot_of(w.get("name", ""))
        if slot:
            worn_names[slot] = w.get("name", "")
    best: dict[str, dict[str, Any]] = {}
    for item in items:
        slot, kind = slot_of(item.get("name", ""))
        if not slot:
            continue
        if min_level and int(item.get("level", 0)) < min_level:
            continue
        if slot == "оружие" and kind != weapon_kind:
            continue
        if int(item.get("gold", 0)) > max_gold:
            continue
        # лимит «не больше 3 золота на вещь» — считаем всю сумму в серебре
        if int(item.get("gold", 0)) * 100 + int(item.get("silver", 0)) > max_gold * 100:
            continue
        if max_silver and int(item.get("silver", 0)) > max_silver:
            continue
        if slot in bought_slots:
            continue
        if not item.get("price_ok", True):
            continue  # цену не распознали — покупать вслепую нельзя
        if require_better and int(item.get("bonus", 0)) <= 0:
            continue  # не лучше надетого — дубль, покупать не нужно
        if int(item.get("bonus", 0)) < min_bonus:
            continue  # прирост слишком мал — не тратим деньги
        if avoid_same_name and worn_names.get(slot, "") == item.get("name", ""):
            continue  # чистый дубль надетой вещи
        current = best.get(slot)
        if current is None or int(item.get("bonus", 0)) > int(current.get("bonus", 0)):
            best[slot] = item
    return sorted(best.values(), key=lambda x: -int(x.get("bonus", 0)))


def parse_lots(html: str, resource: str) -> list[dict[str, Any]]:
    """Разбор лотов аукциона ресурсов из HTML страницы.

    resource: bottles | mifril | iron. Возвращает список лотов:
    {'amount': int, 'gold': int, 'silver': int, 'price_silver': int}
    (цена в серебре: 1 золото = 100 серебра).
    """
    icon = _RESOURCE_ICONS.get(resource)
    lots: list[dict[str, Any]] = []
    for match in _LOT_RE.finditer(html):
        if icon and match.group("res") != icon:
            continue
        amount = parse_amount(match.group("qty"))
        if not amount:
            continue
        money = match.group("money")
        gold_match = _GOLD_RE.search(money)
        silver_match = _SILVER_RE.search(money)
        gold = parse_amount(gold_match.group(1)) if gold_match else 0
        silver = parse_amount(silver_match.group(1)) if silver_match else 0
        price = gold * 100 + silver
        lots.append(
            {
                "amount": amount,
                "gold": gold,
                "silver": silver,
                "price_silver": price,
                "unit_price_silver": price / amount if amount else 0.0,
            }
        )
    return lots


def best_unit_price(lots: list[dict[str, Any]]) -> float:
    """Максимальная цена за единицу среди лотов (серебро на штуку)."""
    prices = [lot.get("unit_price_silver", 0.0) for lot in lots if lot.get("amount")]
    return max(prices) if prices else 0.0


def median_unit_price(lots: list[dict[str, Any]]) -> float:
    """Рыночная цена за единицу — медиана по лотам.

    Максимум брать нельзя: среди лотов есть и завышенные (55 мфр за 4 зол 55 с),
    а минимум — распродажа дешёвых партий. Медиана адекватно отражает рынок.
    """
    prices = sorted(lot.get("unit_price_silver", 0.0) for lot in lots if lot.get("amount"))
    if not prices:
        return 0.0
    middle = len(prices) // 2
    if len(prices) % 2:
        return prices[middle]
    return (prices[middle - 1] + prices[middle]) / 2


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text.replace("&nbsp;", " "))


def parse_well(html: str) -> dict[str, Any]:
    """Состояние колодца удачи: доступен ли подарок и книга за железо."""
    info = {
        "gift_available": "getDailyGiftLink" in html,
        "book_available": "getBookLink" in html,
        "book_iron": None,
    }
    match = re.search(r"Пожертвовать\s*([\d\s]+)\s*железа", _strip_tags(html))
    if match:
        info["book_iron"] = parse_amount(match.group(1))
    return info


def parse_ironmaster(html: str) -> list[dict[str, Any]]:
    """Варианты покупки опыта у мудреца: [{percent, gold?, iron?}]."""
    text = _strip_tags(html)
    options: list[dict[str, Any]] = []
    pattern = re.compile(
        r"Получить\s+([\d\s]+)\s*\(\s*([\d.,]+)\s*%\s*\)\s*опыта.{0,200}?"
        r"Пожертвовать\s+([\d\s]+)\s*(железа|золота)"
    )
    for match in pattern.finditer(text):
        percent = float(match.group(2).replace(",", "."))
        amount = parse_amount(match.group(3))
        currency = "iron" if "желез" in match.group(4).lower() else "gold"
        options.append(
            {
                "percent": percent,
                "currency": currency,
                "amount": amount,
                "xp": parse_amount(match.group(1)),
            }
        )
    return options


def parse_autocrack(html: str) -> list[dict[str, str]]:
    """Доступные переключатели авторазбора: [{kind, label, href}]."""
    found: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a[^>]*href="[^"]*(?P<kind>autoCrack\w+Link)[^"]*"[^>]*>(?P<label>.*?)</a>',
        html,
        re.S,
    ):
        label = re.sub(r"<[^>]+>", " ", match.group("label"))
        label = re.sub(r"\s+", " ", label).strip()
        found.append({"kind": match.group("kind"), "label": label})
    return found


def bazaar_lots(game: Game, resource: str) -> list[dict[str, Any]]:
    """Лоты текущей вкладки аукциона ресурсов."""
    return parse_lots(game.p.content(), resource)


def well_state(game: Game) -> dict[str, Any]:
    return parse_well(game.p.content())


def ironmaster_options(game: Game) -> list[dict[str, Any]]:
    return parse_ironmaster(game.p.content())


def autocrack_options(game: Game) -> list[dict[str, str]]:
    return parse_autocrack(game.p.content())


def fmt_amount(value: int | None) -> str:
    if value is None:
        return "?"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


__all__ = [
    "FightTarget",
    "ClanQuest",
    "Talent",
    "home_targets",
    "classify_target",
    "fightmore_options",
    "dungeon_list",
    "clan_quests",
    "talents",
    "donate_controls",
    "storage_text",
    "resources_summary",
    "parse_lots",
    "best_unit_price",
    "median_unit_price",
    "parse_well",
    "parse_ironmaster",
    "parse_autocrack",
    "bazaar_lots",
    "well_state",
    "ironmaster_options",
    "autocrack_options",
    "fmt_amount",
    "parse_amount",
]
