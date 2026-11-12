r"""Мобильная эмуляция Одноклассников: заставить ok.ru отдавать мобильную версию.

Зачем
----
ОК выбирает версию сайта по User-Agent, но «Варвары» (appId=128512) в каталоге
ОК зарегистрированы как Direct Game (мобильное приложение): веб-клиента у игры
в каталоге нет, вместо него ОК рисует плашку «Игра доступна только на мобильных
платформах» (mob_only_app, data-app-client="noapp").

Этот скрипт даёт настоящую мобильную эмуляцию, а не одну подмену UA:
  * User-Agent iPhone/Android;
  * client hints (Sec-CH-UA-Mobile: ?1, Sec-CH-UA-Platform);
  * сенсорный экран, узкий вьюпорт, device_scale_factor, has_touch;
  * постоянный профиль — сессия ОК переживает перезапуск.

Что он делает
-------------
1. Открывает мобильный ОК (вход — вручную в окне браузера, пароль в чат не передаётся).
2. Ждёт настоящую авторизацию (появление сессионной куки sid).
3. Обходит страницы: страница игры, мобильная карточка приложения m.ok.ru/app/barbars,
   раздел «Игры» профиля.
4. По каждой странице сохраняет HTML, скриншот, список iframe и — главное —
   все найденные точки входа: ссылки кнопок «Играть/Открыть/Запустить», deeplink'и
   (okapp://, market://), адреса игровых хостов.

Запуск
------
    python tools\ok_phone.py                     # окно браузера, вход вручную
    python tools\ok_phone.py --headless          # облако (Linux + xvfb)
    python tools\ok_phone.py --skip-login        # без входа, только разведка
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

# Клиентские подсказки: без них ОК считает сессию десктопной.
MOBILE_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
    "Sec-CH-UA-Platform-Version": '"13.0.0"',
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Upgrade-Insecure-Requests": "1",
}

INTERESTING = re.compile(
    r"(okapp://|market://|itms-apps://|playok|barbar|overmobile|apiok|"
    r"/game/|appId=128512|apps\.|store|userapi|bridge)",
    re.IGNORECASE,
)

BUTTON_WORDS = ("Играть", "Открыть", "Запустить", "Установить", "Играть в", "Play")

PAGES = [
    ("m-app", "https://m.ok.ru/app/barbars"),
    ("game", "https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512"),
    ("m-game", "https://m.ok.ru/game/barbars"),
    ("profile-games", "https://m.ok.ru/profile"),
]


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def has_session(page) -> bool:
    """Проверка входа: у ОК сессионные куки domain_sid / sid."""
    try:
        cookies = page.context.cookies()
    except Exception:  # noqa: BLE001
        return False
    for c in cookies:
        if c["name"] in ("domain_sid", "sid") and c.get("value"):
            return True
    return False


def collect_entrypoints(html: str) -> dict[str, list[str]]:
    """Ищем в HTML всё, что может быть точкой входа в игру."""
    patterns = {
        "deeplink": r'(?:okapp|market|itms-apps|intent)://[^"\'\\\s<>]{4,200}',
        "launch_url": r'"(?:webUrl|webGameUrl|launchUrl|launchUri|playUri|gameUrl|appUrl|url)"\s*:\s*"(https?://[^"]{4,200})"',
        "app_client": r'data-app-client="([^"]+)"',
        "mob_only": r'mob_only_app',
        "iframe": r'<iframe[^>]*src="([^"]{4,300})"',
        "appid": r'(?:st\.appId=|appId["\':= ]{1,6})(\d{4,10})',
        "game_hosts": r'https?://[^"\'\\\s<>]*(?:barbar|overmobile|playok)[^"\'\\\s<>]{0,80}',
    }
    out: dict[str, list[str]] = {}
    for name, pat in patterns.items():
        found = list(dict.fromkeys(re.findall(pat, html, re.IGNORECASE)))
        if found:
            out[name] = found[:25]
    return out


def find_buttons(page) -> list[dict]:
    """Кнопки запуска игры вместе с их ссылками/обработчиками."""
    found: list[dict] = []
    for word in BUTTON_WORDS:
        try:
            els = page.query_selector_all(f"a, button, [role='button']")
        except Exception:  # noqa: BLE001
            continue
        for el in els:
            try:
                text = (el.inner_text() or "").strip()
            except Exception:  # noqa: BLE001
                continue
            if word.lower() not in text.lower() or len(text) > 40:
                continue
            info = {"text": text}
            for attr in ("href", "data-href", "data-url", "data-cmd", "onclick"):
                try:
                    val = el.get_attribute(attr)
                except Exception:  # noqa: BLE001
                    val = None
                if val:
                    info[attr] = val[:300]
            if len(info) > 1:
                found.append(info)
    return found[:40]


def main() -> int:
    ap = argparse.ArgumentParser(description="Мобильная эмуляция ОК")
    ap.add_argument("--url", default="", help="страница для первого открытия")
    ap.add_argument("--profile", default="profile-ok-phone")
    ap.add_argument("--out", default="logs/ok-phone")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--android", action="store_true", help="Android UA вместо iPhone")
    ap.add_argument("--skip-login", action="store_true")
    ap.add_argument("--login-timeout", type=int, default=900)
    ap.add_argument("--watch", type=int, default=12, help="пауза на каждой странице, сек")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=844)
    args = ap.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    profile = ROOT / args.profile
    ua = ANDROID_UA if args.android else IPHONE_UA

    log(f"профиль: {profile.name} | UA: {'Android' if args.android else 'iPhone'} | "
        f"headless={args.headless} | прошлый вход: {has_session.__name__}")

    net_log: list[dict] = []
    report: dict = {"time": stamp, "pages": []}

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(profile),
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

        def on_request(req) -> None:
            try:
                if INTERESTING.search(req.url):
                    net_log.append({"method": req.method, "url": req.url})
            except Exception:  # noqa: BLE001
                pass

        ctx.on("request", on_request)

        # 1. Открываем ОК и ждём входа.
        start_url = args.url or "https://m.ok.ru/"
        log(f"открываю {start_url}")
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка перехода: {exc}")

        if not args.skip_login:
            if has_session(page):
                log("сессия уже есть — вход не требуется")
            else:
                log("НУЖНА АВТОРИЗАЦИЯ: войдите в ОК в открывшемся окне браузера.")
                deadline = time.time() + args.login_timeout
                while time.time() < deadline and not has_session(page):
                    time.sleep(2)
                log("авторизация получена" if has_session(page)
                    else "ВХОД НЕ ЗАВЕРШЁН — продолжаю в анонимном режиме")

        # 2. Обходим страницы.
        for name, url in PAGES:
            if args.skip_login and name != "game":
                continue
            log(f"--- страница [{name}] {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:  # noqa: BLE001
                log(f"   ошибка перехода: {exc}")
                continue
            time.sleep(args.watch)
            try:
                page.wait_for_timeout(1200)
            except Exception:  # noqa: BLE001
                pass

            try:
                html = page.content()
            except Exception:  # noqa: BLE001
                html = ""
            (out_dir / f"{name}-{stamp}.html").write_text(html, encoding="utf-8")
            try:
                page.screenshot(path=str(out_dir / f"{name}-{stamp}.png"))
            except Exception as exc:  # noqa: BLE001
                log(f"   скриншот не удался: {exc}")

            try:
                body = " ".join(page.inner_text("body").split())
            except Exception:  # noqa: BLE001
                body = ""
            try:
                frames = [f.url for f in page.frames]
            except Exception:  # noqa: BLE001
                frames = []
            entries = collect_entrypoints(html)
            buttons = find_buttons(page)

            report["pages"].append({
                "name": name,
                "url": page.url,
                "title": page.title(),
                "session": has_session(page),
                "body_head": body[:900],
                "frames": frames,
                "entrypoints": entries,
                "buttons": buttons,
            })
            log(f"   url={page.url}")
            log(f"   сессия={has_session(page)} app-client={entries.get('app_client')}")
            log(f"   кадры={frames}")
            log(f"   текст: {body[:220]}")
            if buttons:
                log(f"   кнопки: {json.dumps(buttons, ensure_ascii=False)[:600]}")
            if entries:
                log(f"   входы: {json.dumps(entries, ensure_ascii=False)[:600]}")

        report["network"] = net_log[-150:]
        (out_dir / f"report-{stamp}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(f"отчёт: {out_dir / f'report-{stamp}.json'}")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
