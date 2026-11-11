"""Патч: если клановое задание взять не удалось — не повторять попытку каждый цикл.

Без этого агент зацикливался на шаге «взять задание» и переставал фармить
(кнопки «Взять задание» нет, если задание уже занято другим игроком клана).
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "loop.py"
text = path.read_text(encoding="utf-8")

old = '''        # если очко таланта не потратилось (кнопки нет) — не пытаемся заново
        # каждый цикл, иначе агент не доходит до фарма
        self.talent_blocked_until: float = 0.0'''
new = '''        # если очко таланта не потратилось (кнопки нет) — не пытаемся заново
        # каждый цикл, иначе агент не доходит до фарма
        self.talent_blocked_until: float = 0.0
        # аналогично для клановых заданий: если «Взять задание» недоступно
        # (задание занято другим игроком), возвращаемся к нему позже
        self.quest_blocked_until: float = 0.0'''
assert old in text, "не найден talent_blocked_until"
text = text.replace(old, new, 1)

old = '''        state.autocrack_kind = self.autocrack_kind'''
new = '''        state.autocrack_kind = self.autocrack_kind
        if self.quest_blocked_until > time.time():
            state.quests = []'''
assert old in text, "не найдено место для autocrack_kind"
text = text.replace(old, new, 1)

old = '''        if self.game.take_clan_quest(index):
            self.log(f"взято клановое задание: {decision.target}")
        else:
            self.log("задание не взято (кнопка не найдена)")'''
new = '''        if self.game.take_clan_quest(index):
            self.log(f"взято клановое задание: {decision.target}")
        else:
            self.quest_blocked_until = time.time() + 900
            self.log("задание не взято (кнопка не найдена) — вернусь к заданиям через 15 мин")'''
assert old in text, "не найден _do_quest"
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("патч применён")
