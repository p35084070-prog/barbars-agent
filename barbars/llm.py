"""LLM-советник на Claude API.

Работает только там, где правила неоднозначны: выбор цели боя, приоритет таланта,
непонятки в интерфейсе. При отсутствии ключа или ошибке API молча возвращается None,
и агент продолжает работать по правилам.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

KNOWLEDGE = """
Игра «Варвары» (barbars.ru), бой пошаговый, всё на сервере:
- У героя: сила, здоровье, энергия, регенерация, броня. Энергия — это «заряд меча»:
  чем полнее, тем сильнее удар; расходуется на удары и умения, восстанавливается сама.
- Шанс крита зависит от максимальной энергии; броня режет входящий урон (макс 75%).
- Класс: воин (бьёт) или медик (лечит союзников и жжёт энергию врагам).
- Умения имеют перезарядку: в бою показывается «(готово)» — значит можно применять.
- Бесплатные бои в сутки ограничены (обычно 2 в подземельях и 3 в дуэлях),
  дополнительный бой стоит 1 золото.
- Опыт героя и «участие» клана капают от боёв; опыт клана = участие / sqrt(участников).
- Снаряжение теряет прочность в бою, чинится железом («Починить все вещи за N»).
- Железо добывается разбором вещей, мифрил — из пещер и клановых заданий.
- Таланты: очко за каждый уровень с 10-го; есть общие ветки и 4 специализации.
- Клан: уровень, опыт, звёзды, задания (берутся кнопкой «Взять задание»), хранилище.
""".strip()


@dataclass
class LlmAnswer:
    choice: str
    reason: str = ""
    raw: str = ""


class ClaudeAdvisor:
    """Тонкая обёртка над Anthropic API с лимитом вызовов в час."""

    def __init__(self, config: dict[str, Any]):
        cfg = config.get("llm", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.model = cfg.get("model", "claude-sonnet-4-5")
        self.max_calls_per_hour = int(cfg.get("max_calls_per_hour", 60))
        self.max_tokens = int(cfg.get("max_tokens", 700))
        self._calls: list[float] = []
        self._client = None
        self.api_key = os.environ.get(cfg.get("api_key_env", "ANTHROPIC_API_KEY"), "").strip()
        self._enabled_cache: bool | None = None

    # ------------------------------------------------------------------ инфраструктура

    def available(self) -> bool:
        if self._enabled_cache is not None:
            return self._enabled_cache
        if not self.enabled or not self.api_key:
            self._enabled_cache = False
            return False
        try:
            from anthropic import Anthropic  # type: ignore

            self._client = Anthropic(api_key=self.api_key)
            self._enabled_cache = True
        except Exception:
            self._enabled_cache = False
        return self._enabled_cache

    def _budget_left(self) -> bool:
        now = time.time()
        self._calls = [t for t in self._calls if now - t < 3600]
        return len(self._calls) < self.max_calls_per_hour

    def _ask(self, system: str, user: str) -> str | None:
        if not self.available() or not self._budget_left():
            return None
        try:
            response = self._client.messages.create(  # type: ignore[union-attr]
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            parts = []
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    parts.append(block.text)
            text = "\n".join(parts).strip()
            self._calls.append(time.time())
            return text
        except Exception as exc:  # сеть, лимиты, биллинг — молча откатываемся к правилам
            print(f"[llm] ошибка API: {exc}")
            return None

    # ------------------------------------------------------------------ сценарии

    def choose_target(self, state_summary: str, options: list[dict[str, str]]) -> str | None:
        """Выбрать цель боя. Возвращает href выбранного варианта."""
        if not options:
            return None
        opts = "\n".join(f"- [{i}] {o['title']} ({o.get('note', '')})" for i, o in enumerate(options))
        prompt = (
            f"Состояние героя: {state_summary}\n\n"
            f"Доступные цели:\n{opts}\n\n"
            "Выбери одну цель, которая быстрее всего качает уровень, участие клана и опыт, "
            "без траты золота. Ответь ТОЛЬКО JSON: "
            '{"index": <номер цели>, "reason": "краткое объяснение"}'
        )
        raw = self._ask(
            "Ты — стратег для браузерной игры «Варвары». Отвечай строго JSON без пояснений.",
            prompt,
        )
        return self._pick(raw, options)

    def choose_talent(self, state_summary: str, talents: list[dict[str, Any]]) -> str | None:
        """Выбрать талант для прокачки. Возвращает имя таланта."""
        if not talents:
            return None
        opts = "\n".join(
            f"- {t['name']} [{t.get('spent', 0)}/{t.get('max', 10)}]{' (изучено)' if t.get('studied') else ''}"
            for t in talents
        )
        prompt = (
            f"Состояние героя: {state_summary}\n"
            f"Класс героя: медик (лечит и жжёт энергию).\n\n"
            f"Доступные таланты:\n{opts}\n\n"
            "Выбери один талант, который стоит прокачать следующим для медика. "
            "Ответь ТОЛЬКО JSON: {\"name\": \"<название таланта>\", \"reason\": \"...\"}"
        )
        raw = self._ask(
            "Ты — билдер персонажа в игре «Варвары». Отвечай строго JSON.",
            prompt,
        )
        if not raw:
            return None
        data = self._parse(raw)
        if not data:
            return None
        name = str(data.get("name", "")).strip()
        if not name:
            return None
        for t in talents:
            if t["name"].lower() == name.lower():
                return t["name"]
        return None

    def interpret_page(self, snippet: str, question: str) -> str | None:
        """Свободный вопрос про незнакомый экран (например, куда вкладывать железо)."""
        prompt = (
            f"Фрагмент страницы игры «Варвары»:\n---\n{snippet[:4000]}\n---\n"
            f"Вопрос: {question}\n"
            "Ответь кратко и по делу, на русском. Если в тексте нет ответа — напиши 'НЕТ'."
        )
        return self._ask("Ты знаешь интерфейс игры «Варвары».", prompt)

    # ------------------------------------------------------------------ утилиты

    @staticmethod
    def _parse(raw: str) -> dict | None:
        if not raw:
            return None
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def _pick(self, raw: str | None, options: list[dict[str, str]]) -> str | None:
        if not raw:
            return None
        data = self._parse(raw)
        if not data:
            return None
        index = data.get("index")
        try:
            index = int(index)
        except (TypeError, ValueError):
            return None
        if not (0 <= index < len(options)):
            return None
        return options[index].get("href")


__all__ = ["ClaudeAdvisor", "LlmAnswer", "KNOWLEDGE"]
