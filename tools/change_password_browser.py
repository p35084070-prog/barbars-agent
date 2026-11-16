"""Смена пароля героя через браузер (страница «Защита аккаунта»).

Запуск: python tools\\change_password_browser.py <ник> <старый_пароль> <новый_пароль> [--update-secret <аккаунт>]
"""
from __future__ import annotations

import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def form_fields(page) -> list[dict[str, str]]:
    out = []
    for el in page.locator("input").all():
        try:
            out.append(
                {
                    "name": el.get_attribute("name") or "",
                    "type": el.get_attribute("type") or "",
                    "placeholder": (el.get_attribute("placeholder") or "")[:40],
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return out


def main() -> int:
    nick, old_pw, new_pw = sys.argv[1], sys.argv[2], sys.argv[3]
    account = ""
    if "--update-secret" in sys.argv:
        idx = sys.argv.index("--update-secret")
        account = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else ""

    with sync_playwright() as pw:
        ctx = pw.chromium.launch(headless=True)
        page = ctx.new_page(
            user_agent=UA,
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            locale="ru-RU",
        )
        page.set_default_timeout(20_000)
        try:
            page.goto("https://barbars.ru/login", wait_until="domcontentloaded")
            page.fill("input[name='login']", nick)
            page.fill("input[name='password']", old_pw)
            page.click("input[type='submit'], button:has-text('Войти')")
            page.wait_for_load_state("domcontentloaded")
            print("после входа:", page.url)
            print("текст:", " ".join(page.inner_text("body").split())[:300])

            page.goto("https://barbars.ru/user/protection/0/1", wait_until="domcontentloaded")
            print("\nстраница защиты:", page.url)
            print("текст:", " ".join(page.inner_text("body").split())[:800])
            fields = form_fields(page)
            print("поля:", fields)

            filled = []
            for f in fields:
                name = (f["name"] or "").lower()
                if not name:
                    continue
                if "pass" not in name and "new" not in name and "old" not in name:
                    continue
                value = new_pw
                if "old" in name or "current" in name or "wrong" in name:
                    value = old_pw
                try:
                    page.fill(f"input[name='{f['name']}']", value)
                    filled.append(f["name"])
                except Exception as exc:  # noqa: BLE001
                    print("не заполнил", f["name"], exc)
            print("заполнено:", filled)
            page.click("input[type='submit'], button:has-text('Сохранить'), button:has-text('Установить'), button:has-text('Изменить')")
            try:
                page.wait_for_load_state("domcontentloaded")
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(1500)
            print("после отправки:", page.url)
            after = " ".join(page.inner_text("body").split())[:600]
            print("текст:", after)
        finally:
            ctx.close()

    # проверка входа с новым паролем
    with sync_playwright() as pw:
        ctx = pw.chromium.launch(headless=True)
        page = ctx.new_page(user_agent=UA, locale="ru-RU")
        page.set_default_timeout(20_000)
        try:
            page.goto("https://barbars.ru/login", wait_until="domcontentloaded")
            page.fill("input[name='login']", nick)
            page.fill("input[name='password']", new_pw)
            page.click("input[type='submit'], button:has-text('Войти')")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1000)
            body = " ".join(page.inner_text("body").split())
            entered = "Регистрация" not in body[:200] and "Войти" not in body[:120]
            print("\nвход с новым паролем:", "успешно" if entered else body[:200])
        finally:
            ctx.close()

    if account:
        subprocess.run(
            ["gh", "secret", "set", f"BARBARS_{account.upper()}_PASSWORD",
             "-R", "p35084070-prog/barbars-agent"],
            input=new_pw,
            text=True,
            check=True,
        )
        print(f"секрет BARBARS_{account.upper()}_PASSWORD обновлён")
    print("PASSWORD_CHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
