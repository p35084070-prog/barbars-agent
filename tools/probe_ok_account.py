"""Локальная проверка ОК-аккаунта: вход по логину/паролю + чей это герой.

Зачем: пароль ОК найден в локальном профиле браузера. Надо понять, это
аккаунт Вагиджана (id 1286381) или qdal (1596900), и заодно получить
живую сессию для секрета OK_SESSION_B64.

В браузере задан прокси 127.0.0.1:8899 — он пускает трафик мимо VPN-туннеля,
где ломается TLS до ok.ru.

Запуск:
    python tools\probe_ok_account.py --login <логин> --password <пароль>
"""
from __future__ import annotations

import argparse
import base64
import gzip
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
MOBILE_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
}
ESSENTIAL = {"domain_sid", "sid", "JSESSIONID", "ENVOY_JSESSIONID", "remixerp",
             "user_id", "lp", "__last_online", "fpId", "tkn", "bci"}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def has_session(ctx) -> bool:
    """Есть ли авторизованная сессия.

    ОК ставит разные маркеры в зависимости от версии: remixerp/user_id,
    либо просто уходит с формы входа на ленту. Поэтому считаем сессией и
    наличие sid-куки у logged_user_id в приложении.
    """
    try:
        names = {c["name"] for c in ctx.cookies()}
    except Exception:  # noqa: BLE001
        return False
    return bool({"remixerp", "user_id", "st_key", "lp"} & names) or "sid" in names


def dump_cookies(ctx) -> None:
    try:
        for c in ctx.cookies():
            log(f"  cookie {c['domain']:14} {c['name']:20} = {str(c.get('value'))[:40]}")
    except Exception as exc:  # noqa: BLE001
        log(f"куки не прочитаны: {exc}")


def login_form(page) -> bool:
    for sel in ("input[name='st.email']", "input[name='st.password']"):
        try:
            if page.locator(sel).count() == 0:
                return False
        except Exception:  # noqa: BLE001
            return False
    return True


def logged_in(page) -> bool:
    """ОК после входа уводит на ленту: форма входа исчезает.

    Признак входа — на странице нет полей логина и есть лента/профиль.
    """
    try:
        if page.locator("input[name='st.email']").count():
            return False
        url = page.url or ""
    except Exception:  # noqa: BLE001
        return False
    if any(mark in url for mark in ("/login", "/welcome", "/registration")):
        return False
    try:
        text = " ".join(page.inner_text("body").split())[:4000]
    except Exception:  # noqa: BLE001
        return False
    return any(mark in text for mark in ("Моя страница", "Добавить", "Лента",
                                         "Друзья", "Сообщения", "Выйти"))


def do_login(page, login: str, password: str) -> str:
    try:
        page.fill("input[name='st.email']", login, timeout=15000)
        page.fill("input[name='st.password']", password, timeout=15000)
        page.press("input[name='st.password']", "Tab", timeout=5000)
    except Exception as exc:  # noqa: BLE001
        return f"не удалось заполнить форму: {str(exc).splitlines()[0]}"
    try:
        page.get_by_role("button", name="Войти", exact=True).click(timeout=8000)
        return ""
    except Exception:
        pass
    for sel in ("button[type='submit']", "input[type='submit']", "button:has-text('Войти')"):
        try:
            page.locator(sel).first.click(timeout=8000)
            return ""
        except Exception:  # noqa: BLE001
            continue
    try:
        page.press("input[name='st.password']", "Enter", timeout=8000)
        return ""
    except Exception as exc:  # noqa: BLE001
        return f"не удалось отправить форму: {str(exc).splitlines()[0]}"


def export(ctx, out_dir: Path) -> tuple[int, int]:
    cookies = ctx.cookies()
    session = {c["name"]: c for c in cookies
               if "ok.ru" in c["domain"] or c["name"] in ESSENTIAL}
    payload = {"ua": IPHONE_UA, "cookies": list(session.values()),
               "at": datetime.now().isoformat(timespec="seconds")}
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=1).encode()
    (out_dir / "ok-session.json").write_bytes(raw)
    packed = base64.b64encode(gzip.compress(raw)).decode()
    (out_dir / "ok-session.b64").write_text(packed, encoding="utf-8")
    return len(session), len(packed)


def main() -> int:
    ap = argparse.ArgumentParser(description="Проверка ОК-аккаунта и экспорт сессии")
    ap.add_argument("--login", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--proxy", default="http://127.0.0.1:8899")
    ap.add_argument("--profile", default="profile-ok-probe-login")
    ap.add_argument("--out", default="")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else ROOT / "logs_local" / "ok-session"
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / args.profile),
            headless=True,
            viewport={"width": 390, "height": 844},
            user_agent=IPHONE_UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
            extra_http_headers=MOBILE_HEADERS,
            proxy={"server": args.proxy} if args.proxy else None,
            args=["--disable-blink-features=AutomationControlled", "--touch-events=enabled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            for url in ("https://m.ok.ru/", "https://ok.ru/"):
                log(f"открываю {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                except Exception as exc:  # noqa: BLE001
                    log(f"ошибка перехода: {exc}")
                    continue
                time.sleep(4)
                if has_session(ctx) or logged_in(page):
                    log("сессия уже есть")
                    break
                if not login_form(page):
                    log("формы входа нет")
                    continue
                err = do_login(page, args.login, args.password)
                if err:
                    log(f"ошибка входа: {err}")
                    continue
                deadline = time.time() + args.timeout
                while time.time() < deadline:
                    time.sleep(3)
                    if has_session(ctx) or logged_in(page):
                        log("✅ вход выполнен")
                        break
                else:
                    log("❌ вход не завершился")
                    body = " ".join(page.inner_text("body").split())
                    body = body.replace(args.login, "[логин]").replace(args.password, "[пароль]")
                    log("страница: " + body[:500])
                    dump_cookies(ctx)
                    ctx.close()
                    return 4

            if not (has_session(ctx) or logged_in(page)):
                log("❌ сессия не получена")
                dump_cookies(ctx)
                ctx.close()
                return 4

            # Кто это: id героя из handshake-URL и имя аккаунта
            log("открываю карточку игры")
            try:
                page.goto("https://m.ok.ru/app/barbars", wait_until="domcontentloaded",
                          timeout=60_000)
                time.sleep(12)
            except Exception as exc:  # noqa: BLE001
                log(f"ошибка перехода к игре: {exc}")

            hero_ids = set()
            for frame in page.frames:
                try:
                    m = re.search(r"logged_user_id=(\d+)", frame.url)
                except Exception:  # noqa: BLE001
                    continue
                if m:
                    hero_ids.add(m.group(1))
                if "od.barbars.ru" in (frame.url or ""):
                    log(f"кадр игры: {frame.url[:160]}")
            log(f"hero_id из handshake: {sorted(hero_ids) or 'не найден'}")

            try:
                text = " ".join(page.inner_text("body").split())
                log("текст карточки: " + text[:400])
            except Exception:  # noqa: BLE001
                pass

            count, size = export(ctx, out_dir)
            log(f"✅ сессия сохранена: {count} cookie, {size} байт → {out_dir}")
            ctx.close()
            return 0
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка: {str(exc).splitlines()[0]}")
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass
            return 1


if __name__ == "__main__":
    sys.exit(main())
