"""Человечные паузы и поведение: рандомные интервалы, «палево»-защита.

Никакого обхода античита «из коробки» здесь нет — просто темп работы, который
не выглядит как идеальный цикл робота: интервалы всегда разные, иногда бывают
длинные паузы, курсор идёт к кнопке по дуге, страница иногда прокручивается.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class HumanConfig:
    enabled: bool = True
    action_delay_min: float = 0.9
    action_delay_max: float = 3.4
    page_delay_min: float = 1.3
    page_delay_max: float = 4.8
    fight_delay_min: float = 0.8
    fight_delay_max: float = 2.6
    long_pause_chance: float = 0.06
    long_pause_min: float = 9.0
    long_pause_max: float = 26.0
    mouse_jitter: bool = True
    scroll_chance: float = 0.25

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "HumanConfig":
        data = data or {}
        known = {f: getattr(cls, f) for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class Humanizer:
    """Генерирует паузы и микродвижения."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.cfg = HumanConfig.from_dict(config)
        self._rng = random.Random()

    # ------------------------------------------------------------------ паузы

    def pause(self, kind: str = "action", factor: float = 1.0) -> None:
        """Пауза перед/после действия нужного типа."""
        if not self.cfg.enabled:
            return
        low, high = {
            "action": (self.cfg.action_delay_min, self.cfg.action_delay_max),
            "page": (self.cfg.page_delay_min, self.cfg.page_delay_max),
            "fight": (self.cfg.fight_delay_min, self.cfg.fight_delay_max),
        }.get(kind, (self.cfg.action_delay_min, self.cfg.action_delay_max))
        delay = self._rng.uniform(low, high) * factor
        time.sleep(max(0.0, delay))

    def maybe_long_pause(self, kind: str = "action") -> bool:
        """Редкая длинная пауза — как будто человек отвлёкся."""
        if not self.cfg.enabled:
            return False
        if self._rng.random() >= self.cfg.long_pause_chance:
            return False
        delay = self._rng.uniform(self.cfg.long_pause_min, self.cfg.long_pause_max)
        time.sleep(delay)
        return True

    # ------------------------------------------------------------------ мышь

    def move_mouse_to(self, page: Any, locator: Any) -> None:
        """Провести курсор к элементу по ломаной линии в несколько шагов."""
        if not self.cfg.enabled or not self.cfg.mouse_jitter:
            return
        try:
            box = locator.bounding_box()
        except Exception:
            return
        if not box:
            return
        target_x = box["x"] + box["width"] / 2
        target_y = box["y"] + box["height"] / 2
        try:
            start = page.mouse.position
            steps = self._rng.randint(6, 14)
            for index in range(1, steps + 1):
                ratio = index / steps
                wobble_x = self._rng.uniform(-25, 25) * (1 - ratio)
                wobble_y = self._rng.uniform(-18, 18) * (1 - ratio)
                page.mouse.move(
                    start["x"] + (target_x - start["x"]) * ratio + wobble_x,
                    start["y"] + (target_y - start["y"]) * ratio + wobble_y,
                )
                time.sleep(self._rng.uniform(0.008, 0.045))
            page.mouse.move(target_x, target_y)
            time.sleep(self._rng.uniform(0.05, 0.25))
        except Exception:
            return

    # ------------------------------------------------------------------ страница

    def maybe_scroll(self, page: Any) -> None:
        """Иногда «прокрутить и вернуться» — как будто читает страницу."""
        if not self.cfg.enabled or self._rng.random() >= self.cfg.scroll_chance:
            return
        try:
            delta = self._rng.choice([120, 180, 240, -150, -220])
            page.mouse.wheel(0, delta)
            time.sleep(self._rng.uniform(0.2, 0.8))
            page.mouse.wheel(0, -delta)
            time.sleep(self._rng.uniform(0.1, 0.4))
        except Exception:
            return
