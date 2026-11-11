"""Проходит обучение нового героя (демо-бой «Долина варваров»).

Аккаунт создан, но остался на странице туториала: нужно нажать «Сразиться!»,
отыграть демо-бой и выйти через «Покинуть бой».
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-firewhite"
CRED_FILE = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt")
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def log(message: str) -> None:
    print(f"{message}", flush=True)


def main() -> int:
    user, password = CRED_FILE.read_text(encoding="utf-8").splitlines()[:2]
    log(f"вход как {user}")
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=True, user_agent=UA,
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
            locale="ru-RU",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
        page.fill("input[name='login']", user)
        page.fill("input[name='password']", password)
        page.click("input[type='submit']")
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
        log(f"после входа: {page.url}")

        for step in range(60):
            body = " ".join(page.inner_text("body").split())
            log(f"шаг {step}: {page.url} :: {body[:120]}")

            if "Выход" in body and "Мой герой" in body:
                log("герой готов, игра доступна")
                ctx.close()
                return 0

            if "Сразиться" in body:
                link = page.query_selector("a:has-text('Сразиться')")
                if link:
                    log("нажимаю «Сразиться!»")
                    link.click()
                    page.wait_for_load_state("domcontentloaded", timeout=60_000)
                    continue

            hit = None
            for word in ("Бить варвара", "Атаковать", "Удар", "бить"):
                hit = page.query_selector(f"a:has-text('{word}')")
                if hit:
                    log(f"нажимаю «{word}»")
                    break
            if hit:
                try:
                    hit.click(timeout=8000)
                except Exception as exc:  # noqa: BLE001
                    log(f"клик не удался: {exc}")
                page.wait_for_timeout(1200)
                continue

            leave = page.query_selector("a:has-text('Покинуть бой')")
            if leave:
                log("покидаю бой")
                leave.click()
                page.wait_for_load_state("domcontentloaded", timeout=60_000)
                continue

            cont = None
            for word in ("Продолжить приключения", "Продолжить", "Далее", "Принять"):
                cont = page.query_selector(f"a:has-text('{word}')") or page.query_selector(
                    f"input[value*='{word}']"
                )
                if cont:
                    log(f"нажимаю «{word}»")
                    break
            if cont:
                try:
                    cont.click(timeout=8000)
                except Exception as exc:  # noqa: BLE001
                    log(f"клик не удался: {exc}")
                page.wait_for_timeout(1500)
                continue

            log("нечего нажимать, жду")
            time.sleep(2)
        ctx.close()
    log("обучение не завершено")
    return 1


if __name__ == "__main__":
    sys.exit(main())
