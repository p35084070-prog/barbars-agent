"""Путь к форме регистрации: свежая сессия -> /start -> «Сразиться!» -> поля."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-fw"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def dump(page, label: str) -> None:
    print(f"=== {label} :: url={page.url} title={page.title()}")
    for el in page.query_selector_all("input, select, textarea, button"):
        tag = el.evaluate("e => e.tagName")
        print("   ", {"tag": tag, "name": el.get_attribute("name"),
                      "type": el.get_attribute("type"), "value": el.get_attribute("value")})
        if tag == "SELECT":
            for opt in el.query_selector_all("option"):
                print("        option:", opt.get_attribute("value"), "|", (opt.inner_text() or "").strip())
    print("   текст:", " ".join(page.inner_text("body").split())[:800])


with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )
    ctx.clear_cookies()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://barbars.ru/start", wait_until="domcontentloaded", timeout=60_000)
    dump(page, "свежая сессия /start")

    fight = page.query_selector("a:has-text('Сразиться')")
    print("fight link:", fight.get_attribute("href") if fight else None)
    if fight:
        fight.click()
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
    dump(page, "после «Сразиться»")
    ctx.close()
