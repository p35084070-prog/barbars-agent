"""Ищем героя в списке «Без клана» (по страницам) и разбираем его строку."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-firewhite"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
URL = (
    "https://barbars.ru/users/online?wicket:bookmarkablePage="
    ":com.overmobile.combats.wicket.pages.online.GuildSearchPage"
)

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
    for step in range(12):
        html = page.content()
        text = " ".join(page.inner_text("body").split())
        found = "fire white" in html.lower()
        print(f"страница {step}: найден={found} len={len(html)} :: {text[:160]}", flush=True)
        if found:
            idx = html.lower().find("fire white")
            print(html[max(0, idx - 800) : idx + 800])
            (ROOT / "knowledge" / "discovered" / "no-clan-row.html").write_text(html, encoding="utf-8")
            break
        nxt = page.query_selector("a:has-text('вперед')")
        if not nxt:
            print("дальше некуда")
            break
        nxt.click()
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
    ctx.close()
