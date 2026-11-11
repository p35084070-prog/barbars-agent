# Перенос агентов «Варвары» в облако (VPS / Linux)

Агент — это Python + Playwright (Chromium). На сервере он крутится 24/7 в headless-режиме:
на вашем ПК не открывается ни окно браузера, ни консоль, ПК можно выключать.

## 1. Взять сервер

Подойдёт любой Ubuntu 22.04/24.04 VPS:

| Провайдер | Минимальный тариф | Оплата |
|---|---|---|
| Timeweb Cloud | «Start» (1 vCPU, 1 ГБ RAM) | ~150–200 ₽/мес |
| reg.ru VPS | «1 ядро / 1 ГБ» | ~250–400 ₽/мес |
| Selectel | «Standart» | ~300 ₽/мес |
| Oracle Cloud Free Tier | 2 ARM-ядра, 1 ГБ RAM | бесплатно (нужна карта для проверки) |

Требования: Ubuntu/Debian, 1 vCPU, 1 ГБ RAM, 20 ГБ диска, статический или «серый» IP (игра
работает и через динамический IP, но при смене IP может потребоваться повторный вход).

## 2. Залить проект и поставить

С ПК:

```powershell
cd "C:\Users\Богдан\Documents\Богдан MINIMAX\barbars-agent"
python deploy\make_cloud_configs.py          # соберёт облачные конфиги
scp -r . user@<ip>:/tmp/barbars-agent
ssh user@<ip> 'sudo bash /tmp/barbars-agent/deploy/install.sh'
```

`install.sh` поставит зависимости, Chromium, systemd-юниты и запустит три сервиса.

## 3. Учётные данные

На сервере создаются файлы (ник в первой строке, пароль во второй):

```bash
sudo mkdir -p /opt/barbars-agent/credentials
sudo nano /opt/barbars-agent/credentials/keis.txt
sudo nano /opt/barbars-agent/credentials/firewhite.txt
sudo chmod 600 /opt/barbars-agent/credentials/*.txt
```

Пароли в репозиторий не попадают: файл лежит вне проекта, права 600, пользователь `barbars`.

## 4. Проверка

```bash
systemctl status barbars-keis barbars-firewhite barbars-clan-watch
journalctl -u barbars-firewhite -f
ls -l /opt/barbars-agent/logs/keis /opt/barbars-agent/logs/firewhite
```

## 5. Что делают сервисы

- `barbars-keis` — первый аккаунт (клановый лидер): алтарь железом, рынок, бои, вклад железа в клан.
- `barbars-firewhite` — второй аккаунт (`fire white ii`): фарм башни, бесплатные бои, авторазбор,
  продажа мифрила/бутылок по медианной цене.
- `barbars-clan-watch` — раз в 15 минут проверяет уровень второго героя; если он 11+,
  лидер приглашает его в клан «Слепые ТИТАНЫ» и повышает до генерала.

## 6. Откат на ПК

Остановить на сервере: `sudo systemctl stop barbars-keis barbars-firewhite barbars-clan-watch`.
Локальные скрипты: `start_agent.ps1`, `start_agent_firewhite.ps1`, `start_clan_watch.ps1`.
