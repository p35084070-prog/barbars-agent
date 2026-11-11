"""Запуск «Варваров» через мобильную версию Одноклассников.

Идея: ОК отдаёт заглушку «Недоступно на данной платформе» только для десктопного
User-Agent. Поэтому поднимаем Chromium в мобильной эмуляции (iPhone: мобильный UA,
сенсорный экран, узкий вьюпорт) и открываем m.ok.ru/game/barbars.

Пароль в чат не передаётся: если открылась форма входа, пользователь вводит данные
сам в открывшемся окне Chromium, скрипт только наблюдает и фиксирует результат.

Запуск:  python tests\ok_mobile_play.py
Логи:    logs/ok-mobile-<date>.log, скриншоты: logs/ok-mobile-*.png
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-ok-mobile"
LOGS = ROOT / "logs"
GAME_URL = "https://m.ok.ru/game/barbars"
RUN_SECONDS = 60 * 60

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)


def log(message: str) -> None:
    line = f"{datetime.now():%H:%M:%S} {message}"
    print(line, flush=True)


def detect_state(page) -> str:
    """Грубая классификация текущей страницы."""
    try:
        url = page.url
        title = page.title()
    except Exception:  # noqa: BLE001
        return "unknown"
    try:
        body = page.inner_text("body", timeout=5000)[:4000]
    except Exception:  # noqa: BLE001
        body = ""
    blob = f"{title}\n{body}"
    if re.search(r"Войти|Пароль|Восстановить пароль|phone|логин", blob, re.IGNORECASE) and page.frames == [page.main_frame]:
        if re.search(r"войти|пароль|логин", blob, re.IGNORECASE):
            return "login"
    if "Недоступно на данной платформе" in blob:
        return "stub"
    if page.frames and len(page.frames) > 1:
        return "game-frames"
    if re.search(r"Играть|Варвары", blob, re.IGNORECASE):
        return "app-page"
    return "other"


def describe(page) -> str:
    parts = [f"url={page.url}", f"title={page.title()!r}"]
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            parts.append(f"iframe[{frame.url[:120]}]")
        except Exception:  # noqa: BLE001
            pass
    return " | ".join(parts)


def main() -> int:
    LOGS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shot_dir = LOGS / f"ok-mobile-{stamp}"
    shot_dir.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            user_agent=IPHONE_UA,
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            is_mobile=True,
            has_touch=True,
            locale="ru-RU",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        log(f"окно запущено, UA мобильный, профиль {PROFILE.name}")
        log(f"перехожу на {GAME_URL}")
        try:
            page.goto(GAME_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка перехода: {exc}")

        deadline = time.time() + RUN_SECONDS
        last_state = ""
        shot_index = 0
        while time.time() < deadline:
            try:
                state = detect_state(page)
                if state != last_state:
                    log(f"состояние: {state} :: {describe(page)}")
                    last_state = state
                    shot_index += 1
                    try:
                        (shot_dir / f"{shot_index:03d}-{state}.html").write_text(
                            page.content(), encoding="utf-8"
                        )
                    except Exception as exc:  # noqa: BLE001
                        log(f"html-дамп не удался: {exc}")
                    try:
                        page.screenshot(path=str(shot_dir / f"{shot_index:03d}-{state}.png"))
                        log(f"скриншот: {shot_index:03d}-{state}.png")
                    except Exception as exc:  # noqa: BLE001
                        log(f"скриншот не удался: {exc}")
                    try:
                        text = page.inner_text("body", timeout=5000)
                        log("текст страницы: " + " ".join(text.split())[:300])
                    except Exception as exc:  # noqa: BLE001
                        log(f"текст не прочитан: {exc}")
                if state in ("game-frames", "app-page") and page.frames:
                    for frame in page.frames:
                        if frame != page.main_frame:
                            log(f"кадр игры: {frame.url}")
                if state == "game-frames":
                    shot_index += 1
                    page.screenshot(path=str(shot_dir / f"{shot_index:03d}-game.png"))
            except Exception as exc:  # noqa: BLE001
                log(f"ошибка наблюдения: {exc}")
            time.sleep(5)

        context.close()
    log("готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
