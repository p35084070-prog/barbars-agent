"""Новый герой в каталоге кланов: ищем кнопку вступления."""
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
    for url in (
        "https://barbars.ru/rating/guild",
        "https://barbars.ru/?wicket:bookmarkablePage=:com.overmobile.combats.wicket.pages.guild.GuildFormPage",
    ):
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        print(f"=== {page.url}")
        print("текст:", " ".join(page.inner_text("body").split())[:350])
        html = page.content()
        for item in re.findall(r"[^\"'<>]{0,70}(?:вступи|Приглаш|приглаш|Хочу|хочу)[^\"'<>]{0,70}", html, re.I):
            print("    html:", " ".join(item.split())[:160])
        for href, text in page.eval_on_selector_all(
            "a", "els => els.map(e => [e.getAttribute('href'), (e.innerText||'').trim().slice(0,40)])"
        ):
            if text and ("guild" in (href or "").lower() or "клан" in text.lower() or "вступ" in text.lower()):
                print("   ссылка:", href, "|", text)
    ctx.close()
