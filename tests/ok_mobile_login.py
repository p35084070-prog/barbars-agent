"""Мобильный вход в ОК для приложения «Варвары» (appId 128512).

Окно Chromium в мобильной эмуляции (iPhone UA) открывает страницу приложения
в ОК. Если требуется вход — пользователь вводит данные сам, пароль в чат не
передаётся. Скрипт ждёт авторизацию, затем нажимает «Играть» и следит за тем,
появился ли игровой клиент.

Запуск:  python tests\\ok_mobile_login.py
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-ok-mobile"
LOGS = ROOT / "logs"
APP_URL = "https://m.ok.ru/app/barbars"
RUN_SECONDS = 60 * 90

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def page_text(page) -> str:
    try:
        return page.inner_text("body", timeout=5000)
    except Exception:  # noqa: BLE001
        return ""


def state_of(page, text: str) -> str:
    if re.search(r"Войти|войти по номеру|логин|пароль", text[:1500], re.IGNORECASE):
        if page.query_selector("input[type=password]"):
            return "login"
    if page.query_selector("input[type=password]"):
        return "login"
    if "mob_only_app" in text:
        return "mob-only"
    frames = [f.url for f in page.frames if f != page.main_frame]
    game_frames = [u for u in frames if "barbar" in u.lower() or "overmobile" in u.lower() or "webgame" in u.lower()]
    if game_frames:
        return "game"
    if re.search(r"Играть|Открыть|Установить", text, re.IGNORECASE):
        return "launchable"
    return "other"


def main() -> int:
    LOGS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shots = LOGS / f"ok-mobile-login-{stamp}"
    shots.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            user_agent=IPHONE_UA,
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            locale="ru-RU",
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        log(f"окно мобильного ОК запущено, профиль {PROFILE.name}")
        try:
            page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка перехода: {exc}")

        deadline = time.time() + RUN_SECONDS
        last = ""
        index = 0
        launched = False
        while time.time() < deadline:
            text = page_text(page)
            state = state_of(page, text)
            if state != last:
                log(f"состояние: {state} :: url={page.url}")
                log("текст: " + " ".join(text.split())[:220])
                for frame in page.frames:
                    if frame != page.main_frame:
                        log(f"  кадр: {frame.url[:140]}")
                index += 1
                try:
                    page.screenshot(path=str(shots / f"{index:03d}-{state}.png"))
                except Exception as exc:  # noqa: BLE001
                    log(f"скриншот не удался: {exc}")
                try:
                    (shots / f"{index:03d}-{state}.html").write_text(page.content(), encoding="utf-8")
                except Exception:
                    pass
                last = state

            if state == "launchable" and not launched:
                for word in ("Играть", "Открыть"):
                    link = page.query_selector(f"a:has-text('{word}')")
                    if link:
                        log(f"нажимаю «{word}»")
                        try:
                            link.click(timeout=8000)
                        except Exception as exc:  # noqa: BLE001
                            log(f"клик не удался: {exc}")
                        launched = True
                        time.sleep(4)
                        break

            time.sleep(4)
        ctx.close()
    log("готово")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
