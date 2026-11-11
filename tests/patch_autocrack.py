"""Патч driver.py: корректная обработка режима авторазбора «обычные вещи»."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "driver.py"
text = path.read_text(encoding="utf-8")

old = '''    def set_autocrack(self, kind: str) -> bool:
        """Включить авторазбор: kind = autoCrackCommonLink | autoCrackUncommonLink | ..."""
        self.goto("https://barbars.ru/user/rack/autocrack")
        return self.click_href(kind)
'''

new = '''    def autocrack_active(self) -> str | None:
        """Какой режим авторазбора включён сейчас.

        На странице активный пункт выводится текстом без ссылки, остальные —
        ссылками. Поэтому «нет ссылки» + «текст есть» = этот режим включён.
        """
        labels = (
            ("autoCrackOffLink", "Не разбирать вещи"),
            ("autoCrackCommonLink", "обычные вещи"),
            ("autoCrackUncommonLink", "необычные вещи и хуже"),
            ("autoCrackRareLink", "редкие вещи и хуже"),
            ("autoCrackEpicLink", "эпические вещи и хуже"),
            ("autoCrackLegendaryLink", "легендарные вещи и хуже"),
        )
        text = self.body_text().lower()
        for href, label in labels:
            if self.p.locator(f"a[href*='{href}']").count() > 0:
                continue
            if label.lower() in text:
                return href
        return None

    def set_autocrack(self, kind: str) -> bool:
        """Включить авторазбор: kind = autoCrackCommonLink | autoCrackUncommonLink | ...

        Режим «обычные вещи» (autoCrackCommonLink) на странице не является
        ссылкой — он уже включён по умолчанию, поэтому кликать нечего.
        """
        self.goto("https://barbars.ru/user/rack/autocrack")
        if self.click_href(kind):
            return True
        return self.autocrack_active() == kind
'''

if old in text:
    path.write_text(text.replace(old, new), encoding="utf-8")
    print("патч применён")
else:
    print("фрагмент не найден — уже пропатчено?")
