"""Страница «Без клана» глазами нового героя: ищем «Хочу в клан»."""
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

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(
        "https://barbars.ru/users/online?wicket:bookmarkablePage=:com.overmobile.combats.wicket.pages.online.GuildSearchPage",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    html = page.content()
    (ROOT / "knowledge" / "discovered" / "no-clan-new.html").write_text(html, encoding="utf-8")
    print("текст:", " ".join(page.inner_text("body").split())[:500])
    idx = html.find("fire white")
    print("=== наш герой найден:", idx > 0)
    if idx > 0:
        print(html[max(0, idx - 600) : idx + 600])
    for item in re.findall(r"[^\"'<>]{0,120}(?:\(\+\)|Хочу|хочу)[^\"'<>]{0,120}", html):
        print("   mark:", " ".join(item.split())[:200])
    ctx.close()
