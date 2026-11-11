"""Кликает «Регистрация» на гостевой странице игры (как живой пользователь)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "profile-fw4")
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
    page.goto("https://barbars.ru/guild/16675", wait_until="domcontentloaded", timeout=60_000)
    print("гость:", page.url, "|", " ".join(page.inner_text("body").split())[:200])
    link = page.query_selector("a:has-text('Регистрация')")
    print("ссылка:", link.get_attribute("href") if link else None)
    if link:
        link.click()
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
    print("после клика:", page.url, "|", " ".join(page.inner_text("body").split())[:300])
    print("поля:", [el.get_attribute("name") for el in page.query_selector_all("input,select")])
    (ROOT / "knowledge" / "discovered" / "registration-click.html").write_text(page.content(), encoding="utf-8")
    for tag in re.findall(r"<(?:input|select)[^>]*>", page.content(), re.IGNORECASE):
        print("   ", " ".join(tag.split()))
    ctx.close()
