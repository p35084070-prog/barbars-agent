"""Разбор содержимого ключевых страниц игры: список целей боя, задания клана, таланты."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .driver import Game, parse_amount


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
