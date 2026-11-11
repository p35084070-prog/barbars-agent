"""Открыть отдельное окно браузера с firewhite (для просмотра героя).

Использует отдельный профиль (profile-view-firewhite), поэтому сессия
не пересекается с keis во встроенном браузере и не с облачными агентами.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DESKTOP = Path(r"C:\Users\Богдан\Desktop")
CRED = DESKTOP / "barbars-firewhite-credentials.txt"
PROFILE = Path(__file__).resolve().parents[1] / "profile-view-firewhite"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in CRED.read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    nick, password = lines[0], lines[1]
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE), headless=False, viewport={"width": 1280, "height": 900},
            user_agent=UA, args=["--window-size=1300,950"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://barbars.ru/login", wait_until="domcontentloaded")
        page.fill("input[name='login']", nick)
        page.fill("input[name='password']", password)
        page.click("input[type='submit'], button[type='submit']")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        if "login" in page.url and re.search(r"Вход для игроков", page.content()):
            print("ВХОД НЕ УДАЛСЯ")
            return 1
        page.goto("https://barbars.ru/user", wait_until="domcontentloaded")
        print("вошли как", nick, "| страница:", page.url)
        print("окно открыто, не закрываю — смотрите героя. Закройте окно, когда надоест.")
        while True:
            time.sleep(30)
            if ctx.pages == []:
                break
    return 0


if __name__ == "__main__":
    sys.exit(main())
