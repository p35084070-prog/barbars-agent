"""Патч: экипировка лучших вещей + сброс лишнего в сундук (рюкзак забит → опыт стоит)."""
from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- driver.py
path = root / "barbars" / "driver.py"
text = path.read_text(encoding="utf-8")

anchor = "    def autocrack_active(self) -> str | None:"
assert anchor in text, "не найден автocrack_active"

methods = '''    # ------------------------------------------------------------------ рюкзак и вещи

    @staticmethod
    def _item_blocks(html: str) -> list[tuple[str, str]]:
        """Разбить страницу рюкзака на блоки предметов: (html блока, href индекса)."""
        blocks: list[tuple[str, str]] = []
        for chunk in html.split('<div class="hr"></div>'):
            m = re.search(r'href="([^"]*items:(\\d+):(?:wearLink|toStoreLink)[^"]*)"', chunk)
            if m:
                blocks.append((chunk, m.group(2)))
        return blocks

    def bag_counts(self) -> dict[str, int]:
        """Сколько мест в рюкзаке и сундуке, и сколько занято."""
        self.goto("https://barbars.ru/user/rack")
        text = self.body_text()
        out = {"bag_used": 0, "bag_total": 0, "chest_used": 0, "chest_total": 0}
        m = re.search(r"Рюкзак\\s*\\((\\d+)\\s*/\\s*(\\d+)\\)", text)
        if m:
            out["bag_used"], out["bag_total"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"Открыть сундук\\s*\\((\\d+)\\s*/\\s*(\\d+)\\)", text)
        if m:
            out["chest_used"], out["chest_total"] = int(m.group(1)), int(m.group(2))
        return out

    def equip_better_items(self, limit: int = 8) -> int:
        """Надеть вещи, помеченные «Лучше (+N)» — герой становится сильнее."""
        worn = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/rack")
            html = self.p.content()
            target = None
            for chunk, index in self._item_blocks(html):
                if "Лучше" in chunk and f"items:{index}:wearLink" in chunk:
                    target = index
                    break
            if target is None:
                break
            if not self.click_href(f"items:{target}:wearLink"):
                break
            worn += 1
        return worn

    def stash_items(self, keep: int = 4, limit: int = 20) -> int:
        """Сложить лишние вещи в сундук, чтобы освободить рюкзак.

        Сначала убираем вещи без пометки «Лучше» (они хуже надетых).
        """
        moved = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/rack")
            text = self.body_text()
            m = re.search(r"Рюкзак\\s*\\((\\d+)\\s*/\\s*(\\d+)\\)", text)
            used = int(m.group(1)) if m else 0
            if used <= keep:
                break
            m = re.search(r"Открыть сундук\\s*\\((\\d+)\\s*/\\s*(\\d+)\\)", text)
            if m and int(m.group(1)) >= int(m.group(2)):
                break  # сундук полон
            html = self.p.content()
            target = None
            for chunk, index in self._item_blocks(html):
                if f"items:{index}:toStoreLink" in chunk and "Лучше" not in chunk:
                    target = index
                    break
            if target is None:
                for chunk, index in self._item_blocks(html):
                    if f"items:{index}:toStoreLink" in chunk:
                        target = index
                        break
            if target is None:
                break
            if not self.click_href(f"items:{target}:toStoreLink"):
                break
            moved += 1
        return moved

'''

text = text.replace(anchor, methods + anchor, 1)
path.write_text(text, encoding="utf-8")
print("driver.py: добавлены методы рюкзака")

# ---------------------------------------------------------------- rules.py
path = root / "barbars" / "rules.py"
text = path.read_text(encoding="utf-8")

old = '''    # 9. Фарм башни: бесплатные бои, капает опыт, железо, бутылочки и вещи.'''
new = '''    # 9. Рюкзак: надеть лучшие вещи и убрать лишнее в сундук.
    #    Забитый рюкзак блокирует новый дроп — из-за этого встаёт опыт.
    gear = _pick_gear(state, config)
    if gear is not None:
        return gear

    # 10. Фарм башни: бесплатные бои, капает опыт, железо, бутылочки и вещи.'''
assert old in text, "не найден шаг башни"
text = text.replace(old, new, 1)

helper = '''def _pick_gear(state: GameState, config: dict[str, Any]) -> Decision | None:
    """Разбор рюкзака: надеть лучшее, лишнее — в сундук.

    Включается флагом `gear.enabled`. Если рюкзак и сундук полны, включает
    более агрессивный авторазбор (`gear.overflow_crack`), чтобы дропы
    превращались в железо, а не копились.
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
    if used <= keep:
        return None
    overflow = (used >= total) and (chest_used >= chest_total)
    if overflow:
        kind = str(cfg.get("overflow_crack", "autoCrackUncommonLink"))
        if state.autocrack_kind != kind:
            return Decision(
                "autocrack",
                target=kind,
                reason="рюкзак и сундук полны — включаем разбор добычи",
            )
        return None
    return Decision(
        "gear",
        target="рюкзак",
        params={"keep_bag": keep, "max_equip": int(cfg.get("max_equip", 8))},
        reason=f"рюкзак заполнен на {used}/{total} — надеваем лучшее и убираем лишнее",
    )


def _pick_tower('''

text = text.replace("def _pick_tower(", helper, 1)
path.write_text(text, encoding="utf-8")
print("rules.py: добавлен шаг рюкзака")

# ---------------------------------------------------------------- loop.py
path = root / "barbars" / "loop.py"
text = path.read_text(encoding="utf-8")

old = '''        elif decision.action == "tower":
            self._do_tower(decision)'''
new = '''        elif decision.action == "tower":
            self._do_tower(decision)
        elif decision.action == "gear":
            self._do_gear(decision)'''
assert old in text, "не найден обработчик tower"
text = text.replace(old, new, 1)

old_method = '''    def _do_tower(self, decision: rules.Decision) -> None:'''
new_method = '''    def _do_gear(self, decision: rules.Decision) -> None:
        """Надеть лучшие вещи и убрать лишнее в сундук."""
        keep = int(decision.params.get("keep_bag", 4))
        max_equip = int(decision.params.get("max_equip", 8))
        worn = self.game.equip_better_items(limit=max_equip)
        moved = self.game.stash_items(keep=keep)
        counts = self.game.bag_counts()
        self.log(
            f"рюкзак: надето {worn}, в сундук {moved}, "
            f"рюкзак {counts.get('bag_used')}/{counts.get('bag_total')}, "
            f"сундук {counts.get('chest_used')}/{counts.get('chest_total')}"
        )

    def _do_tower(self, decision: rules.Decision) -> None:'''
assert old_method in text, "не найден _do_tower"
text = text.replace(old_method, new_method, 1)

path.write_text(text, encoding="utf-8")
print("loop.py: добавлен обработчик gear")
