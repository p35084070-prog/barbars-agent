"""Патч loop.py: если очко таланта не потратилось — не пытаться каждый цикл.

Без этого агент застревал на шаге «талант» и не доходил до фарма.
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "loop.py"
text = path.read_text(encoding="utf-8")

old_init = '''        # крайний срок работы (0 = работаем бесконечно); нужен в облаке,
        # чтобы аккуратно выйти даже посреди боя
        self.deadline: float = 0.0'''

new_init = '''        # крайний срок работы (0 = работаем бесконечно); нужен в облаке,
        # чтобы аккуратно выйти даже посреди боя
        self.deadline: float = 0.0
        # если очко таланта не потратилось (кнопки нет) — не пытаемся заново
        # каждый цикл, иначе агент не доходит до фарма
        self.talent_blocked_until: float = 0.0'''

assert old_init in text, "не найден __init__"
text = text.replace(old_init, new_init, 1)

old_state = '''        state = rules.collect_state(self.game, self.config)
        self.last_state = state'''

new_state = '''        state = rules.collect_state(self.game, self.config)
        self.last_state = state
        if self.talent_blocked_until > time.time():
            state.talent_points = 0'''

assert old_state in text, "не найден collect_state"
text = text.replace(old_state, new_state, 1)

old_talent = '''        self.log("не удалось потратить очко таланта")'''

new_talent = '''        self.log("не удалось потратить очко таланта — вернусь к талантам позже")
        self.talent_blocked_until = time.time() + 1800'''

assert old_talent in text, "не найден финал _do_talent"
text = text.replace(old_talent, new_talent, 1)

path.write_text(text, encoding="utf-8")
print("патч применён")
