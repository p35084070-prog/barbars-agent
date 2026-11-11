"""Патч: понятное сообщение, если файл учётных данных не найден."""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "barbars" / "driver.py"
text = path.read_text(encoding="utf-8")

old = '''            path = self._credentials_file(raw_file)
            if path.exists():
                lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if len(lines) >= 2:
                    user = user or lines[0]
                    password = password or lines[1]
'''

new = '''            path = self._credentials_file(raw_file)
            if path.exists():
                lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if len(lines) >= 2:
                    user = user or lines[0]
                    password = password or lines[1]
            else:
                print(f"[вход] файл учётных данных не найден: {path}")
'''

assert old in text, "не найден блок чтения учётных данных"
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("патч применён")
