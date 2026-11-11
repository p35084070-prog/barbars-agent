"""Чистый профиль: первый запрос /start — что отдаст сервер."""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "profile-fw2")
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
    resp = page.goto("https://barbars.ru/start", wait_until="domcontentloaded", timeout=60_000)
    print("status:", resp.status if resp else None, "url:", page.url)
    print("текст:", " ".join(page.inner_text("body").split())[:400])
    print("коуки:", [(c["name"], c["value"][:16]) for c in ctx.cookies()])
    fight = page.query_selector("a:has-text('Сразиться')")
    print("есть «Сразиться»:", bool(fight))
    ctx.close()
