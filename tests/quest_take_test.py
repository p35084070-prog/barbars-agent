"""Ручная проверка: берёт ли герой клановое задание (и что с этим дальше)."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CREDS = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt")
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")


def main() -> int:
    user, password = [l.strip() for l in CREDS.read_text(encoding="utf-8-sig").splitlines()[:2]]
    profile = ROOT / "profile-quest-test"
    shutil.rmtree(profile, ignore_errors=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(profile), headless=True, user_agent=UA,
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="ru-RU")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
        page.fill("input[name='login']", user)
        page.fill("input[name='password']", password)
        page.click("input[type='submit']")
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
        page.goto("https://barbars.ru/guild/quests/0/16675", wait_until="domcontentloaded", timeout=60_000)
        body = " ".join(page.inner_text("body").split())
        print("ДО:", body[body.find("Клановые задания"):][:400])
        buttons = page.query_selector_all("a:has-text('Взять задание'), button:has-text('Взять задание')")
        print("найдено кнопок:", len(buttons))
        if buttons:
            print("текст:", repr((buttons[0].inner_text() or "").strip()))
            print("href:", buttons[0].get_attribute("href"))
            buttons[0].click()
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            body2 = " ".join(page.inner_text("body").split())
            print("ПОСЛЕ:", body2[body2.find("Клановые задания"):][:400])
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
