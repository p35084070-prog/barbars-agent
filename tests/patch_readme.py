"""Дополняет README разделом про облачный запуск (GitHub Actions)."""
from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "README.md"
text = path.read_text(encoding="utf-8")

marker = "## Установка"
assert marker in text, "не найден раздел установки"

section = '''## Облачный запуск (GitHub Actions, бесплатно)

Агенты можно крутить не на своём ПК: репозиторий публичный, поэтому минуты
стандартных раннеров GitHub не тарифицируются, и фарм идёт круглосуточно.

Что уже настроено в `.github/workflows/`:

| Workflow | Что делает |
|---|---|
| `agent-keis.yml` | Первый аккаунт (клановый лидер): алтарь, рынок, бои, вклад железа |
| `agent-firewhite.yml` | Второй аккаунт (`fire white ii`): фарм башни, авторазбор, продажа ресурсов |
| `clan-watch.yml` | Раз в 15 минут проверяет уровень нового героя; если 11+ — лидер приглашает его в клан и повышает до генерала |

Схема работы: одно задание = одна длинная сессия (5,5 часа) с одним входом в игру,
в конце сессия сама запускает следующую (через `workflow_dispatch`), а `schedule`
каждые 15–20 минут служит страховкой, если цепочка оборвалась. Параллельные запуски
одного аккаунта невозможны — `concurrency` с группой на аккаунт.

Дневные счётчики (сколько продано, сколько раз брали подарок и т.п.) лежат в
`state/<аккаунт>/daily.json` и коммитятся в репозиторий — иначе после каждой
перезагрузки виртуалки агент считал бы, что день ещё не начался, и превышал лимиты.

Логи сессии складываются в artifacts (`logs/<аккаунт>`), срок хранения 14 дней.

### Секреты

Учётные данные лежат в GitHub Secrets (шифруются, в форки и pull request не попадают):

```
BARBARS_KEIS_LOGIN, BARBARS_KEIS_PASSWORD
BARBARS_FIREWHITE_LOGIN, BARBARS_FIREWHILE_PASSWORD
```

Файл `credentials/<аккаунт>.txt` создаётся на раннере из секретов, права 600.
В репозитории паролей нет — `.gitignore` исключает `credentials*`, `config.json`
и `config-firewhite.json` (локальные конфиги с путями к рабочему столу).

### Запуск вручную

```bash
gh workflow run agent-firewhite.yml -f duration=10 --repo <владелец>/<репозиторий>
gh run list --repo <владелец>/<репозиторий>
```

---

'''

text = text.replace(marker, section + marker, 1)
path.write_text(text, encoding="utf-8")
print("README дополнен")
