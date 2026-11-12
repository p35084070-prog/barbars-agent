r"""Запуск игры «Варвары» через Одноклассники с мобильной эмуляцией.

Зачем
----
«Варвары» в каталоге ОК (appId=128512) размещены как мобильное приложение
(Direct Game). В десктопной версии ok.ru игра не запускается — ОК показывает
плашку «Игра доступна только на мобильных платформах» (mob_only_app).
Но мобильная версия сайта (m.ok.ru/app/barbars) ведёт себя иначе: игра
открывается в iframe на od.barbars.ru и получает подписанные параметры
запуска ОК (logged_user_id, session_key, api_server=api.ok.ru, application_key).

Значит, чтобы играть «через ОК» с компьютера, нужна мобильная эмуляция:
  * мобильный User-Agent;
  * сенсорный экран, узкий вьюпорт, device_scale_factor;
  * авторизованная сессия ОК (постоянный профиль Chromium).

Как пользоваться
----------------
1. Один раз авторизоваться на компьютере:
       python tools\ok_phone.py
   (откроется окно, войдите в ОК руками; пароль в чат не передаётся).
2. Запустить игру:
       python tools\ok_play.py
   Скрипт откроет m.ok.ru/app/barbars, дождётся кадра игры и останется в ней.

В облаке (Linux, без экрана):
       xvfb-run -a python tools\ok_play.py --headless
   Профиль с авторизацией надо перенести на сервер (каталог profile-ok-phone).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

# Точка входа в мобильную карточку приложения: игра открывается в iframe.
GAME_URL = "https://m.ok.ru/app/barbars"
# Запасные адреса, если основной не сработал.
FALLBACK_URLS = [
    "https://m.ok.ru/app/barbars",
    "https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512",
    "https://m.ok.ru/game/barbars",
]

GAME_FRAME = re.compile(r"(od\.barbars\.ru|barbars\.ru)", re.IGNORECASE)
# Признаки живой игры в кадре: у ОК кадр игры может грузиться через
# document.write, и тогда его URL пустой — судим по содержимому.
GAME_MARKERS = ("Сражения", "Торговля", "Мой герой", "Мой клан", "Купить золото")

# Клиентские подсказки: с ними ОК отдаёт мобильную вёрстку и веб-клиент игры.
MOBILE_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
    "Sec-CH-UA-Platform-Version": '"13.0.0"',
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Upgrade-Insecure-Requests": "1",
}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def has_session(page) -> bool:
    try:
        cookies = page.context.cookies()
    except Exception:  # noqa: BLE001
        return False
    return any(c["name"] in ("domain_sid", "sid") and c.get("value") for c in cookies)


def game_frame(page):
    """Кадр с игрой.

    Игра живёт в iframe #appMain_Div на od.barbars.ru, но ОК периодически
    пересоздаёт этот кадр, и Playwright не всегда отдаёт его в page.frames.
    Поэтому ищем iframe в DOM и берём его content_frame().
    """
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            if GAME_FRAME.search(frame.url):
                return frame
        except Exception:  # noqa: BLE001
            continue
    try:
        handle = page.query_selector("iframe#appMain_Div, iframe[src*='barbars.ru']")
    except Exception:  # noqa: BLE001
        handle = None
    if handle is None:
        return None
    try:
        return handle.content_frame()
    except Exception:  # noqa: BLE001
        return None


def game_is_loaded(page) -> bool:
    """Есть ли игровой iframe в DOM страницы."""
    try:
        srcs = page.evaluate(
            "() => Array.from(document.querySelectorAll('iframe')).map(f => f.src)"
        )
    except Exception:  # noqa: BLE001
        return False
    return any("barbars.ru" in s for s in srcs)


def main() -> int:
    ap = argparse.ArgumentParser(description="Игра «Варвары» через ОК")
    ap.add_argument("--profile", default="profile-ok-phone")
    ap.add_argument("--url", default=GAME_URL)
    ap.add_argument("--out", default="logs/ok-play")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--android", action="store_true")
    ap.add_argument("--hold", type=int, default=0, help="сколько секунд остаться в игре")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=844)
    args = ap.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ua = ANDROID_UA if args.android else IPHONE_UA

    log(f"профиль {args.profile} | headless={args.headless}")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / args.profile),
            headless=args.headless,
            viewport={"width": args.width, "height": args.height},
            user_agent=ua,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers=MOBILE_HEADERS,
            args=["--disable-blink-features=AutomationControlled", "--touch-events=enabled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        log(f"открываю {args.url}")
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка перехода: {exc}")

        if not has_session(page):
            log("НЕТ СЕССИИ ОК. Запустите сначала: python tools\\ok_phone.py")
            page.screenshot(path=str(out_dir / f"no-session-{stamp}.png"))
            ctx.close()
            return 2

        frame = None
        for attempt in range(1, 7):
            time.sleep(6)
            if game_is_loaded(page):
                frame = game_frame(page)
                if frame:
                    log(f"игра загрузилась (попытка {attempt})")
                else:
                    log(f"попытка {attempt}: iframe игры в DOM, но кадр ещё не отдан")
                    frame = None
            if frame:
                break
            log(f"попытка {attempt}: кадра игры пока нет")
            if attempt < 6:
                nxt = FALLBACK_URLS[attempt - 1] if attempt - 1 < len(FALLBACK_URLS) else None
                if nxt and nxt != page.url:
                    log(f"   пробую {nxt}")
                    try:
                        page.goto(nxt, wait_until="domcontentloaded", timeout=60_000)
                    except Exception as exc:  # noqa: BLE001
                        log(f"   ошибка: {exc}")

        try:
            page.screenshot(path=str(out_dir / f"game-{stamp}.png"))
        except Exception as exc:  # noqa: BLE001
            log(f"скриншот не удался: {exc}")

        if not game_is_loaded(page):
            log("ИГРА НЕ ЗАГРУЗИЛАСЬ")
            ctx.close()
            return 1

        # Достаём текст из кадра игры — так видно, что аккаунт живой.
        body = ""
        if frame:
            try:
                body = " ".join(frame.inner_text("body").split())[:600]
            except Exception:  # noqa: BLE001
                body = ""
        if not body:
            try:
                body = " ".join(page.inner_text("body").split())[:600]
            except Exception:  # noqa: BLE001
                body = ""
        log(f"текст игры: {body}")

        meta = {"time": stamp, "frame_url": frame.url if frame else "", "game_text": body}
        (out_dir / f"game-{stamp}.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if args.hold:
            log(f"остаюсь в игре {args.hold} сек")
            deadline = time.time() + args.hold
            while time.time() < deadline:
                time.sleep(5)
                if not game_is_loaded(page):
                    log("игра пропала со страницы — перезагружаю")
                    try:
                        page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
                    except Exception as exc:  # noqa: BLE001
                        log(f"   ошибка: {exc}")
                    continue
                f = game_frame(page)
                text = ""
                if f:
                    try:
                        text = " ".join(f.inner_text("body").split())[:200]
                    except Exception:  # noqa: BLE001
                        text = ""
                if not text:
                    try:
                        text = " ".join(page.inner_text("body").split())[:200]
                    except Exception:  # noqa: BLE001
                        text = ""
                log(f"   {text}")

        ctx.close()
    log("готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
