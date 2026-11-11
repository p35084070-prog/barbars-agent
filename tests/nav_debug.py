"""Диагностика навигации barbars.ru в браузере: splash → start → login."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-fw"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", lambda r: print("   <-", r.status, r.url[:110]) if "barbars" in r.url else None)

    page.goto("https://barbars.ru/", wait_until="networkidle", timeout=60_000)
    print("cookies:", [(c["name"], c["value"][:20]) for c in ctx.cookies()])

    print("--- клик по start ---")
    link = page.query_selector("a[href*='start']")
    link.click()
    page.wait_for_timeout(3000)
    print("url:", page.url, "title:", page.title())
    print("текст:", " ".join(page.inner_text("body").split())[:400])

    print("--- клик по «Вход для игроков» ---")
    page.goto("https://barbars.ru/", wait_until="networkidle", timeout=60_000)
    login_link = page.query_selector("a:has-text('Вход для игроков')")
    login_link.click()
    page.wait_for_timeout(3000)
    print("url:", page.url, "title:", page.title())
    print("текст:", " ".join(page.inner_text("body").split())[:400])
    print("поля:", [(el.get_attribute("name"), el.get_attribute("type")) for el in page.query_selector_all("input")])
    ctx.close()
