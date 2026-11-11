"""Патч: бой не должен висеть вечно + сторож зависшего цикла.

1) Ветка «ждём энергию» не увеличивала счётчик ходов — если энергия не
   восстанавливалась, цикл крутился часами без единой строки в логе.
2) Сторож: если цикл агента длится дольше cycle_max_sec, браузер закрывается,
   зависший вызов Playwright падает, и агент перезапускает браузер.
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "loop.py"
text = path.read_text(encoding="utf-8")

# --- 1) счётчик ходов в ветке ожидания энергии
old = '''            elif decision.action == "wait_energy":'''
new = '''            elif decision.action == "wait_energy":
                turns += 1  # иначе ожидание энергии может длиться вечно'''
assert old in text, "не найдена ветка wait_energy"
text = text.replace(old, new, 1)

# --- 2) сторож зависшего цикла
old = '''    def run_once(self) -> rules.Decision:
        if not self.game.browser_alive():'''
new = '''    def run_once(self) -> rules.Decision:
        watchdog = threading.Timer(
            float(self.config.get("run", {}).get("cycle_max_sec", 300)),
            self._abort_cycle,
        )
        watchdog.daemon = True
        watchdog.start()
        try:
            return self._run_once_inner()
        finally:
            watchdog.cancel()

    def _abort_cycle(self) -> None:
        """Сторож: цикл завис — закрываем браузер, агент его перезапустит."""
        self.log("цикл завис дольше лимита — перезапускаю браузер", "WARN")
        try:
            self.game.close()
        except Exception:
            pass

    def _run_once_inner(self) -> rules.Decision:
        if not self.game.browser_alive():'''
assert old in text, "не найден run_once"
text = text.replace(old, new, 1)

if "\nimport threading\n" not in text:
    text = text.replace("import json\nimport time", "import json\nimport threading\nimport time", 1)

path.write_text(text, encoding="utf-8")
print("патч применён")
