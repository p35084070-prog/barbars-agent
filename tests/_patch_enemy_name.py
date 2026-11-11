"""Одноразовый патч: выделение имени противника из первой строки ссылки удара."""

from pathlib import Path

p = Path(r"C:\Users\Богдан\Documents\Богдан MINIMAX\barbars-agent\barbars\driver.py")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
block = '''            if text.startswith("Бить"):
                flat = text.split("\\n")[0].strip()
                cs.attack_links.append(flat)
                cs.enemy_name = flat[len("Бить") :].strip()
            elif text.startswith("Лечить"):
                cs.heal_links.append(text.split("\\n")[0].strip())
            elif text.startswith("Сбежать") or text.startswith("Отступить") or text.startswith("Убежать"):
                cs.flee_links.append(text.split("\\n")[0].strip())
'''
start = next(i for i, l in enumerate(lines) if 'if text.startswith("Бить"):' in l)
end = next(i for i, l in enumerate(lines) if "cs.flee_links.append(text)" in l)
lines[start:end + 1] = [block]
p.write_text("".join(lines), encoding="utf-8")
print("patched lines", start, end)
