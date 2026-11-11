"""Приглашает нового героя в клан: оба аккаунта онлайн одновременно.

Кнопка «Пригласить в клан» показывается в профиле игрока без клана, только если
он сейчас на сайте. Поэтому открываем два профиля в одном браузере:
  A — keis (лидер клана, копия профиля), B — новый герой.
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
KEIS_PROFILE = ROOT / "profile"
KEIS_COPY = ROOT / "profile-keis-copy"
NEW_PROFILE = ROOT / "profile-firewhite"
NEW_CREDS = Path(r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt")
GUILD = "16675"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def log(message: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {message}", flush=True)


def open_ctx(pw, profile: Path):
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(profile), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )
    return ctx


def ensure_new_hero(ctx) -> None:
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
    body = " ".join(page.inner_text("body").split())
    if "Вход для игроков" in body:
        user, password = NEW_CREDS.read_text(encoding="utf-8").splitlines()[:2]
        page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
        page.fill("input[name='login']", user)
        page.fill("input[name='password']", password)
        page.click("input[type='submit']")
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
        body = " ".join(page.inner_text("body").split())
    log(f"новый герой на сайте: {body[:120]}")


def main() -> int:
    if not KEIS_COPY.exists():
        log("копирую профиль keis")
        shutil.copytree(KEIS_PROFILE, KEIS_COPY, dirs_exist_ok=True)

    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, KEIS_PROFILE)
        ctx_b = open_ctx(pw, NEW_PROFILE)

        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_a.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
        body_a = " ".join(page_a.inner_text("body").split())
        if "Вход для игроков" in body_a:
            log("keis: автовход")
            creds = Path(r"C:\Users\Богдан\Desktop\barbars-agentcredentials.txt")
            user, password = creds.read_text(encoding="utf-8").splitlines()[:2]
            page_a.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
            page_a.fill("input[name='login']", user)
            page_a.fill("input[name='password']", password)
            page_a.click("input[type='submit']")
            page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
            body_a = " ".join(page_a.inner_text("body").split())
        log(f"keis на сайте: {body_a[:120]}")

        ensure_new_hero(ctx_b)

        # лидер ищет героя и приглашает
        page_a.goto("https://barbars.ru/users/search", wait_until="domcontentloaded", timeout=60_000)
        page_a.fill("input[name='name']", "fire white ii", timeout=10_000)
        page_a.click("input[type='submit']")
        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
        link = page_a.query_selector("a[href*='user/id/31389504']")
        if not link:
            log("герой не найден в поиске")
            return 3
        link.click()
        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
        log(f"профиль героя: {' '.join(page_a.inner_text('body').split())[:150]}")
        invite = page_a.query_selector("a:has-text('Пригласить в клан')")
        if not invite:
            log("кнопки приглашения нет (герой не онлайн?)")
            page_a.screenshot(path=str(ROOT / "knowledge" / "discovered" / "invite-missing.png"))
            return 4
        invite.click()
        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
        log(f"после приглашения: {' '.join(page_a.inner_text('body').split())[:250]}")

        # новый герой принимает приглашение
        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        page_b.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
        time.sleep(2)
        body_b = " ".join(page_b.inner_text("body").split())
        log(f"герой после приглашения: {body_b[:400]}")
        page_b.screenshot(path=str(ROOT / "knowledge" / "discovered" / "new-hero-invite.png"))
        for word in ("Вступить", "Принять", "Приглашение", "в клан"):
            btn = page_b.query_selector(f"a:has-text('{word}')")
            if btn:
                log(f"нажимаю «{word}»")
                btn.click()
                page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                log(f"стало: {' '.join(page_b.inner_text('body').split())[:300]}")
                break
        page_b.goto(f"https://barbars.ru/guild/{GUILD}", wait_until="domcontentloaded", timeout=60_000)
        log(f"клан: {' '.join(page_b.inner_text('body').split())[:300]}")
        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
