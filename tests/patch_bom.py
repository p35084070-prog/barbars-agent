"""Патч: при чтении файла учётных данных снимать BOM и любые невидимые символы."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]

# 1) driver.py — основной загрузчик
path = root / "barbars" / "driver.py"
text = path.read_text(encoding="utf-8")
old = '''                lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]'''
new = '''                raw = path.read_text(encoding="utf-8-sig")
                lines = [clean_credential(line) for line in raw.splitlines()]
                lines = [line for line in lines if line]'''
if old in text:
    text = text.replace(old, new, 1)
    helper = '''

def clean_credential(value: str) -> str:
    """Убрать BOM и прочие невидимые символы из строки учётных данных.

    Файл с учётными данными может прийти с UTF-8 BOM (например, после
    пересборки в PowerShell) — иначе логин уходит в игру как '\\ufeffник'
    и она отвечает «Неверный ник или пароль».
    """
    return value.strip().lstrip("\\ufeff").strip()
'''
    marker = "\n\nclass Game:"
    assert marker in text, "не найден класс Game"
    text = text.replace(marker, helper + marker, 1)
    path.write_text(text, encoding="utf-8")
    print("driver.py: патч применён")
else:
    print("driver.py: уже пропатчено")

# 2) clan_join_auto.py — вступление в клан
path = root / "tests" / "clan_join_auto.py"
text = path.read_text(encoding="utf-8")
old = '''    user, password = creds.read_text(encoding="utf-8").splitlines()[:2]'''
new = '''    raw = creds.read_text(encoding="utf-8-sig")
    lines = [l.strip().lstrip("\\ufeff").strip() for l in raw.splitlines()]
    lines = [l for l in lines if l]
    user, password = lines[0], lines[1]'''
if old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("clan_join_auto.py: патч применён")
else:
    print("clan_join_auto.py: уже пропатчено")
