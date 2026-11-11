"""Патч rules.py: башня должна проверяться до авторазбора (иначе авторазбор блокирует фарм)."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "rules.py"
text = path.read_text(encoding="utf-8")

tower_block = '''    # 12. Фарм башни: бесплатные бои, капает опыт, железо, бутылочки и вещи.
    #     Основной способ прокачки для новых героев (у них нет клана и подземелий).
    tower = _pick_tower(state, config)
    if tower is not None:
        return tower

'''

if tower_block in text:
    text = text.replace(tower_block, "")
    anchor = "    # 9. Авторазбор вещей в железо/мифрил.\n"
    assert anchor in text, "не найден якорь"
    text = text.replace(
        anchor,
        "    # 9. Фарм башни: бесплатные бои, капает опыт, железо, бутылочки и вещи.\n"
        "    #     Основной способ прокачки для новых героев (у них нет клана и подземелий).\n"
        "    tower = _pick_tower(state, config)\n"
        "    if tower is not None:\n"
        "        return tower\n\n"
        "    # 10. Авторазбор вещей в железо/мифрил.\n",
    )
    # перенумеровать комментарии ниже
    text = text.replace("    # 10. Вклад в хранилище клана", "    # 11. Вклад в хранилище клана")
    text = text.replace("    # 11. Фарм-события", "    # 12. Фарм-события")
    text = text.replace("    # 13. Ничего не делаем", "    # 13. Ничего не делаем")
    path.write_text(text, encoding="utf-8")
    print("порядок шагов обновлён")
else:
    print("блок башни не найден — уже переставлено?")
