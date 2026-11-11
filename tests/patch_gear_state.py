"""Патч: состояние рюкзака и текущий режим авторазбора в GameState + сбор состояния."""
from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]

path = root / "barbars" / "rules.py"
text = path.read_text(encoding="utf-8")

old = '''    # авторазбор
    autocrack_set_today: bool = False'''
new = '''    # авторазбор
    autocrack_set_today: bool = False
    autocrack_kind: str = ""
    # рюкзак и сундук: сколько занято
    bag: dict[str, int] = field(default_factory=dict)'''
assert old in text, "не найдено поле autocrack_set_today"
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("rules.py: добавлены поля bag и autocrack_kind")
