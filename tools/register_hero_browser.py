"""Регистрация нового героя barbars.ru через настоящий браузер (playwright).

Сервер отдаёт форму регистрации не всем сессиям: воронка нового игрока
(«Долина варваров» → «Сразиться!») открывается изредка, и кнопки в
воронке нужно нажать по-настоящему (JS-обработчики Wicket).

Скрипт: открывает /start, жмёт «Сразиться!», если появилась форма регистрации —
заполняет её (ник, пол, сторона, класс) и отправляет.

Запуск: python tools\\register_hero_browser.py <ник> [класс] [сторона] [пароль]
"""
from __future__ import annotations

import json
import random
import re
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

NICK = sys.argv[1] if len(sys.argv) > 1 else "Steel Blue ii"
KIND = sys.argv[2] if len(sys.argv) > 2 else "1"
SIDE = sys.argv[3] if len(sys.argv) > 3 else "1"
PASSWORD = sys.argv[4] if len(sys.argv) > 4 else ("Sb" + secrets.token_urlsafe(12))
MAIL = f"steelblue{random.randint(1000, 9999)}@mailinator.com"
CRED_FILE = ROOT / "credentials-steelblue.json"


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def main() -> int:
    log(f"ник={NICK!r} класс={KIND} сторона={SIDE} пароль={PASSWORD}")
    deadline = time.time() + 60 * 45
    attempt = 0
    with sync_playwright() as pw:
        while time.time() < deadline:
            attempt += 1
            ctx = pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = ctx.new_page(
                user_agent=UA, viewport={"width": 390, "height": 844},
                is_mobile=True, has_touch=True, locale="ru-RU",
            )
            page.set_default_timeout(20_000)
            try:
                page.goto("https://barbars.ru/start", wait_until="domcontentloaded", timeout=45_000)
                body = " ".join(page.inner_text("body").split())
                has_form = page.query_selector("#registrationForm") is not None
                if not has_form:
                    # воронка: жмём «Сразиться!»
                    fight = page.query_selector("a:has-text('Сразиться')")
                    if fight:
                        fight.click(timeout=10_000)
                        page.wait_for_load_state("domcontentloaded", timeout=45_000)
                        body = " ".join(page.inner_text("body").split())
                has_form = page.query_selector("#registrationForm") is not None
                if not has_form:
                    log(f"[{attempt}] формы нет :: {body[:110]}")
                    ctx.close()
                    time.sleep(2 + random.random() * 3)
                    continue
                log(f"[{attempt}] ФОРМА найдена (браузер)")
                page.fill("input[name='login']", NICK)
                page.select_option("select[name='sex']", "m")
                page.select_option("select[name='side']", SIDE)
                page.select_option("select[name='type']", KIND)
                (OUT / "registration-steelblue-form.html").write_text(
                    page.content(), encoding="utf-8"
                )
                page.click("input[type='submit']")
                page.wait_for_load_state("domcontentloaded", timeout=45_000)
                body = " ".join(page.inner_text("body").split())
                log(f"после отправки: {page.url}")
                log("текст: " + body[:600])
                (OUT / "registration-steelblue.html").write_text(page.content(), encoding="utf-8")
                (OUT / "registration-steelblue-session.json").write_text(
                    json.dumps(
                        {c["name"]: c["value"] for c in ctx.cookies()},
                        ensure_ascii=False, indent=2,
                    ),
                    encoding="utf-8",
                )
                CRED_FILE.write_text(
                    json.dumps(
                        {"nick": NICK, "password": PASSWORD, "mail": MAIL},
                        ensure_ascii=False, indent=2,
                    ),
                    encoding="utf-8",
                )
                log("сохранены cookies и учётные данные")
                ctx.close()
                return 0
            except Exception as exc:  # noqa: BLE001
                log(f"[{attempt}] ошибка: {exc}")
                try:
                    ctx.close()
                except Exception:
                    pass
                time.sleep(3 + random.random() * 4)
    log("форма так и не появилась")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
