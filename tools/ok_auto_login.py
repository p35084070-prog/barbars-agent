r"""Автовход в ОК по логину и паролю + экспорт сессии.

Зачем: сессию ОК (cookie sid) раньше приходилось получать вручную — скрипт
открывал окно браузера, человек вводил логин и пароль. Форма входа у ОК
простая (`st.email` + `st.password` + «Войти»), капчи в ней нет, поэтому вход
можно автоматизировать: логин и пароль приходят из переменных окружения
(в CI — из GitHub Secrets) и в репозиторий не попадают.

Что делает:
  1. открывает мобильный ОК (тот же профиль эмуляции, что у ok_phone.py);
  2. заполняет форму и жмёт «Войти»;
  3. ждёт сессионную cookie (sid / domain_sid);
  4. если ОК требует капчу или подтверждение по SMS — честно об этом пишет
     и выходит с кодом 3 (тогда нужен ручной вход, как раньше);
  5. сохраняет сессию в том же формате, что ok_export_cookies.py:
     state/ok-session.json и state/ok-session.b64 (base64+gzip).

Запуск локально:
    python tools\ok_auto_login.py --login <логин> --password <пароль>
В CI:
    OK_LOGIN=... OK_PASSWORD=... python tools\ok_auto_login.py
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
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

# Куки, которые реально нужны для сессии ОК (как в ok_export_cookies.py).
ESSENTIAL = {"domain_sid", "sid", "JSESSIONID", "ENVOY_JSESSIONID", "remixerp",
              "user_id", "lp", "__last_online", "fpId", "tkn", "bci"}

# Признаки того, что ОК просит подтверждение: капча, SMS или фото.
CHALLENGE_MARKERS = (
    "не робот",
    "подтвердите",
    "captcha",
    "капч",
    "код из смс",
    "смс-код",
    "отправьте код",
    "подтверждение",
    "попасть к злоумышленникам",
)


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def has_session(ctx) -> bool:
    """Есть ли авторизованная сессия.

    Одной cookie sid/domain_sid мало: их ОК ставит и анонимным посетителям.
    Признак входа — remixerp/user_id (по ним профиль авторизован).
    """
    try:
        names = {c["name"] for c in ctx.cookies()}
    except Exception:  # noqa: BLE001
        return False
    return bool({"remixerp", "user_id"} & names)


def find_login_form(page) -> bool:
    """Есть ли на странице форма входа по логину и паролю."""
    for sel in ("input[name='st.email']", "input[name='st.password']"):
        try:
            if page.locator(sel).count() == 0:
                return False
        except Exception:  # noqa: BLE001
            return False
    return True


def challenge_on_page(page) -> str:
    """Есть ли на странице требование подтверждения (капча/SMS)."""
    try:
        text = " ".join(page.inner_text("body").split()).lower()
    except Exception:  # noqa: BLE001
        return ""
    for marker in CHALLENGE_MARKERS:
        if marker in text:
            return marker
    return ""


def do_login(page, login: str, password: str) -> str:
    """Заполнить форму и отправить. Возвращает '' при успехе, иначе — причину.

    Кнопка «Войти» на разных страницах ОК отображается по-разному (иногда
    перекрыта баннером), поэтому пробуем несколько способов: клик по кнопке
    отправки, клик с обходом перекрытий и Enter в поле пароля.
    """
    try:
        page.fill("input[name='st.email']", login, timeout=15000)
        page.fill("input[name='st.password']", password, timeout=15000)
    except Exception as exc:  # noqa: BLE001
        return f"не удалось заполнить форму: {str(exc).splitlines()[0]}"

    errors: list[str] = []
    for sel in ("button[type='submit']", "input[type='submit']", "button:has-text('Войти')"):
        try:
            page.locator(sel).first.click(timeout=8000)
            return ""
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sel}: {str(exc).splitlines()[0]}")
    # Запасной путь: клик принудительно, затем Enter в поле пароля.
    for action in ("force-click", "enter"):
        try:
            if action == "force-click":
                page.locator("button[type='submit'], input[type='submit']").first.click(
                    timeout=8000, force=True)
            else:
                page.press("input[name='st.password']", "Enter", timeout=8000)
            return ""
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{action}: {str(exc).splitlines()[0]}")
    return "не удалось отправить форму: " + " | ".join(errors[:3])


def export(ctx, out_dir: Path) -> tuple[int, int]:
    """Сохранить сессию в формате ok_export_cookies.py."""
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
    ap = argparse.ArgumentParser(description="Автовход в ОК по логину и паролю")
    ap.add_argument("--login", default=os.environ.get("OK_LOGIN", ""))
    ap.add_argument("--password", default=os.environ.get("OK_PASSWORD", ""))
    ap.add_argument("--out", default=str(ROOT / "state"))
    ap.add_argument("--profile", default="profile-ok-autologin")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--headed", dest="headless", action="store_false", default=True)
    args = ap.parse_args()

    if not args.login or not args.password:
        log("нет логина/пароля (OK_LOGIN/OK_PASSWORD или --login/--password)")
        return 2

    out_dir = Path(args.out)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / args.profile),
            headless=args.headless,
            viewport={"width": 390, "height": 844},
            user_agent=IPHONE_UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
            extra_http_headers=MOBILE_HEADERS,
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
                time.sleep(3)
                if has_session(ctx):
                    log("сессия уже есть")
                    break
                if not find_login_form(page):
                    log("формы входа нет на этой странице")
                    continue
                err = do_login(page, args.login, args.password)
                if err:
                    log(err)
                    continue
                deadline = time.time() + args.timeout
                while time.time() < deadline:
                    time.sleep(2)
                    if has_session(ctx):
                        log("✅ вход выполнен, сессия получена")
                        break
                    challenge = challenge_on_page(page)
                    if challenge:
                        log(f"⚠️ ОК требует подтверждения («{challenge}») — нужен ручной вход")
                        try:
                            barrier = " ".join(page.inner_text("body").split()).replace(args.login, "[логин скрыт]").replace(args.password, "[пароль скрыт]")
                            barrier = re.sub(r"https?://\S+|\+?\d[\d ()-]{8,}\d", "[скрыто]", barrier)
                            log("защитный экран: " + barrier[:1600])
                            page.screenshot(path=str(ROOT / "logs" / "ok-autologin-challenge.png"))
                        except Exception:  # noqa: BLE001
                            pass
                        ctx.close()
                        return 3
                else:
                    log("вход не завершился за отведённое время")
                    try:
                        text = " ".join(page.inner_text("body").split())
                        safe_text = text.replace(args.login, "[логин скрыт]").replace(args.password, "[пароль скрыт]")
                        log(f"страница: {safe_text[:1600]}")
                        (ROOT / "logs").mkdir(parents=True, exist_ok=True)
                        (ROOT / "logs" / "ok-autologin-lastpage.html").write_text(
                            page.content(), encoding="utf-8")
                    except Exception:  # noqa: BLE001
                        pass
                    ctx.close()
                    return 4

            if not has_session(ctx):
                log("❌ сессия не получена")
                ctx.close()
                return 4
            count, size = export(ctx, out_dir)
            log(f"✅ сессия сохранена: {count} cookie, base64+gz {size} байт")
            ctx.close()
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка: {str(exc).splitlines()[0]}")
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
