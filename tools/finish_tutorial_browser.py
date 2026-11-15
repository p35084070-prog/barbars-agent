"""Проходит туториал нового героя в браузере (playwright).

После регистрации герой попадает на «Долину варваров»: демо-бой («Сразиться!»),
затем «Покинуть бой». Клики нужны настоящие — Wicket обрабатывает их на
сервере, поэтому делаем это через браузер.

Запуск: python tools\\finish_tutorial_browser.py <ник> <пароль>
"""
from __future__ import annotations

import re
import sys
import time

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    with sync_playwright() as pw:
        ctx = pw.chromium.launch(headless=True)
        page = ctx.new_page(
            user_agent=UA, viewport={"width": 390, "height": 844},
            is_mobile=True, has_touch=True, locale="ru-RU",
        )
        page.set_default_timeout(15_000)
        page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
        page.fill("input[name='login']", nick)
        page.fill("input[name='password']", password)
        page.click("input[type='submit']")
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
        print("после входа:", page.url)

        for step in range(120):
            body = " ".join(page.inner_text("body").split())
            print(f"шаг {step}: {page.url} :: {body[:110]}", flush=True)
            if "Выход" in body and "Мой герой" in body:
                print("герой готов")
                ctx.close()
                return 0
            clicked = False
            for word in ("Сразиться", "Бить варвара", "Атаковать"):
                link = page.query_selector(f"a:has-text('{word}')")
                if link:
                    print(f"клик: {word}")
                    try:
                        link.click(timeout=10_000)
                    except Exception as exc:  # noqa: BLE001
                        print("  клик не удался:", exc)
                    page.wait_for_timeout(1500)
                    clicked = True
                    break
            if clicked:
                continue
            leave = page.query_selector("a:has-text('Покинуть бой')")
            if leave:
                print("клик: Покинуть бой")
                leave.click(timeout=10_000)
                page.wait_for_load_state("domcontentloaded", timeout=60_000)
                continue
            for word in ("Продолжить", "Далее", "Принять"):
                link = page.query_selector(f"a:has-text('{word}')") or page.query_selector(
                    f"input[value*='{word}']"
                )
                if link:
                    print(f"клик: {word}")
                    try:
                        link.click(timeout=10_000)
                    except Exception as exc:  # noqa: BLE001
                        print("  клик не удался:", exc)
                    page.wait_for_timeout(1500)
                    clicked = True
                    break
            if not clicked:
                time.sleep(2)
        ctx.close()
    print("туториал не завершён")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
