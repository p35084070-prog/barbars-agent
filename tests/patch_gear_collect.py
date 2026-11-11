"""Патч: собирать состояние рюкзака и текущий режим авторазбора."""
from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[1]

# ---- rules.py: сбор состояния рюкзака
path = root / "barbars" / "rules.py"
text = path.read_text(encoding="utf-8")

old = '''    # 2. Страница героя: статы, опыт, ресурсы, таланты, id героя и клана.
    game.goto("https://barbars.ru/user")'''
new = '''    # 1b. Рюкзак: сколько занято (нужно, чтобы знать, что дроп не влезает).
    if config.get("gear", {}).get("enabled"):
        try:
            state.bag = game.bag_counts()
        except Exception:
            state.bag = {}

    # 2. Страница героя: статы, опыт, ресурсы, таланты, id героя и клана.
    game.goto("https://barbars.ru/user")'''
assert old in text, "не найдено место для сбора рюкзака"
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("rules.py: сбор состояния рюкзака")

# ---- loop.py: помнить текущий режим авторазбора
path = root / "barbars" / "loop.py"
text = path.read_text(encoding="utf-8")

old = '''        self.exp_cache: list[dict[str, Any]] = []
        self.exp_checked_at: float = 0.0'''
new = '''        self.exp_cache: list[dict[str, Any]] = []
        self.exp_checked_at: float = 0.0
        # текущий режим авторазбора (нужно, чтобы не включать его заново)
        self.autocrack_kind: str = ""'''
assert old in text, "не найдено поле exp_cache"
text = text.replace(old, new, 1)

old = '''        kind = decision.target or "autoCrackCommonLink"
        if self.game.set_autocrack(kind):
            self._bump("autocrack", True)
            self.log(f"авторазбор: включён режим {kind}")'''
new = '''        kind = decision.target or "autoCrackCommonLink"
        if self.game.set_autocrack(kind):
            self._bump("autocrack", True)
            self.autocrack_kind = kind
            self.log(f"авторазбор: включён режим {kind}")'''
assert old in text, "не найден _do_autocrack"
text = text.replace(old, new, 1)

old = '''        if self.talent_blocked_until > time.time():
            state.talent_points = 0'''
new = '''        if self.talent_blocked_until > time.time():
            state.talent_points = 0
        state.autocrack_kind = self.autocrack_kind'''
assert old in text, "не найдено место для autocrack_kind"
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("loop.py: учёт режима авторазбора")
