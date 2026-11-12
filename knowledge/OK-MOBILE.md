# Мобильная версия ОК для игры «Варвары» — как открыть игру с компьютера

## Что было не так

«Варвары» в каталоге Одноклассников (appId = **128512**) размещены как **мобильное
приложение** (Direct Game). Из-за этого:

* десктопная страница `ok.ru/game/barbars` отдаёт плашку
  **«Игра доступна только на мобильных платформах»** (`mob_only_app`,
  `data-app-client="noapp"`) — веб-клиента в каталоге ОК просто нет;
* подмена одного `User-Agent` ничего не меняет: ОК смотрит и UA, и client hints,
  и то, с какого домена пришли.

Поэтому прошлые попытки (одна подмена UA, `m.ok.ru` без сессии) и не сработали.

## Что реально работает

Мобильная версия сайта ОК — `m.ok.ru/app/barbars` — ведёт себя иначе. С
авторизованной сессией ОК игра открывается в iframe на `od.barbars.ru` и получает
подписанные параметры запуска:

```
https://od.barbars.ru/odnoklassnikilogin/?container=true&mob=true
    &web_server=https://ok.ru
    &logged_user_id=91889626630
    &session_key=...&session_secret_key=...&auth_sig=...
    &api_server=https://api.ok.ru/
    &application_key=CBAHPCABABABABABA
    &mob_platform=iosweb
```

То есть игра полноценно работает в браузере с компьютера, а её игровой сеанс
идёт через API ОК (`api.ok.ru`) — с подписью и access-токеном ОК.

## Как пользоваться

### 1. Авторизация (один раз, на компьютере)

```powershell
python tools\ok_phone.py
```

Откроется окно браузера с мобильной экранизацией ОК. Войдите в аккаунт руками
(пароль в чат не передаётся). Сессия сохранится в каталоге `profile-ok-phone`
(кука `domain_sid`).

### 2. Запуск игры

```powershell
python tools\ok_play.py            # просто открыть игру
python tools\ok_play.py --hold 600 # открыть и остаться в игре 10 минут
```

Скриншот и отчёт складываются в `logs/ok-play/`.

### Важные детали реализации

| Что | Зачем |
|---|---|
| мобильный UA (iPhone/Android) | ОК выбирает мобильную вёрстку |
| `Sec-CH-UA-Mobile: ?1`, `Sec-CH-UA-Platform` | без client hints ОК считает клиент десктопным |
| `is_mobile`, `has_touch`, вьюпорт 390×844 | мобильные раскладки и тач-обработчики |
| `extra_http_headers` | заголовки нельзя задать иначе, чем через контекст |
| проверка сессии по куке `domain_sid` | у ОК сессионная кука называется `domain_sid`, **а не `sid`** |
| детектор игры по DOM (`iframe#appMain_Div`) | ОК пересоздаёт кадр, и `page.frames` его теряет — проверять надо iframe в DOM |
| адрес входа `m.ok.ru/app/barbars` | на десктопном `ok.ru/game/barbars` игры нет |

## В облаке (Linux-сервер)

Агент на сервере работает headless. Для запуска игры через ОК там нужен
виртуальный экран и перенесённый профиль:

```bash
sudo apt-get install -y xvfb
# профиль с авторизацией копируем с ПК
scp -r profile-ok-phone user@<ip>:/tmp/
ssh user@<ip> 'sudo mv /tmp/profile-ok-phone /opt/barbars-agent/ && sudo chown -R barbars:barbars /opt/barbars-agent/profile-ok-phone'

# запуск
cd /opt/barbars-agent
xvfb-run -a .venv/bin/python -u tools/ok_play.py --headless --hold 3600
```

Сессия ОК живёт ограниченное время — при истечении нужно заново авторизоваться
на ПК и перезалить профиль.

## Что НЕ помогло (проверено)

* одна подмена `User-Agent` (iPhone/Android/WebView) — ОК всё равно редиректит
  на десктопную версию или отдаёт `mob_only_app`;
* `https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512` с разными
  `st.appPlatform` — без разницы;
* `https://m.ok.ru/game/barbars` без авторизации — только анонимная заглушка;
* голый `requests` с мобильным UA — ОК отдаёт страницу, но без сессии игры
  не запускается.

## Файлы

| Файл | Назначение |
|---|---|
| `tools/ok_phone.py` | мобильная эмуляция ОК: авторизация + обход страниц с отчётом |
| `tools/ok_play.py` | запуск «Варваров» через ОК (основной рабочий скрипт) |
| `tools/ok_login_diag.py` | диагностика окна входа: поля, кнопки, куки |
| `tools/ok_probe_frames.py`, `tools/ok_probe_frames2.py` | разбор кадров страницы игры |
| `tools/ok_probe_mobile.py`, `tools/ok_probe_redirect.py` | подбор UA/client hints и разбор редиректов |
| `tools/ok_status_check.py` | поиск статуса «играет» на страницах ОК |
| `tools/ok_probe_catalog.py` | разведка каталога ОК по игре 128512 |
