"""Проверка: откроется ли ОК-приложение «Варвары» (appId=128512) при мобильном User-Agent."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)

ctx = sync_playwright().start()
browser = ctx.chromium.launch_persistent_context(
    str(ROOT / "profile-ok"),
    headless=False,
    viewport={"width": 390, "height": 844},
    user_agent=MOBILE_UA,
    is_mobile=True,
    has_touch=True,
    device_scale_factor=3,
    locale="ru-RU",
)
page = browser.pages[0] if browser.pages else browser.new_page()
try:
    page.goto("https://ok.ru/game/barbars?st.cmd=appMain&st.appId=128512", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    print("URL:", page.url)
    text = page.inner_text("body")[:1500]
    print("ТЕКСТ:", text)
    (ROOT / "knowledge" / "discovered" / "ok-barbars-mobile.html").write_text(
        page.content(), encoding="utf-8"
    )
finally:
    browser.close()
    ctx.stop()
