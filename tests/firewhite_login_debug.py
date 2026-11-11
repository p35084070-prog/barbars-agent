"""Диагностика входа нового героя в браузере."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-firewhite"
CRED_FILE = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt")
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

user, password = CRED_FILE.read_text(encoding="utf-8").splitlines()[:2]
with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
    page.fill("input[name='login']", user)
    page.fill("input[name='password']", password)
    page.click("input[type='submit']")
    page.wait_for_load_state("domcontentloaded", timeout=60_000)
    print("url:", page.url)
    body = " ".join(page.inner_text("body").split())
    print("текст:", body[:600])
    print("есть «Выход»:", "Выход" in body)
    ctx.close()
