"""Что реально открывается по клику на талант (браузер, не requests)."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CREDS = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt")
OUT = ROOT / "knowledge" / "discovered" / "fw-pages"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Mobile Safari/537.36")


def main() -> int:
    user, password = [l.strip() for l in CREDS.read_text(encoding="utf-8-sig").splitlines()[:2]]
    profile = ROOT / "profile-talent-test"
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
        page.goto("https://barbars.ru/user/stances", wait_until="domcontentloaded", timeout=60_000)
        print("=== страница талантов ===")
        print(" ".join(page.inner_text("body").split())[:500])
        link = page.query_selector("a[href*='/user/talent/']")
        if link:
            print("кликаем:", link.get_attribute("href"), "|", link.inner_text())
            link.click()
            page.wait_for_load_state("domcontentloaded", timeout=60_000)
            print("URL после клика:", page.url)
            body = " ".join(page.inner_text("body").split())
            print("текст после клика:", body[:700])
            (OUT / "talent-click.html").write_text(page.content(), encoding="utf-8")
            print("--- ссылки с 'выучить'/'изучить' ---")
            for a in page.query_selector_all("a"):
                t = (a.inner_text() or "").strip()
                if "учить" in t or "зуч" in t or "очко" in t:
                    print("   ", repr(t), a.get_attribute("href"))
            print("--- все ссылки страницы (20) ---")
            for a in page.query_selector_all("a")[:20]:
                print("   ", repr((a.inner_text() or "").strip()[:40]), a.get_attribute("href"))
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
