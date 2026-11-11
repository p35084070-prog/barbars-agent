"""Вступление нового героя в клан и назначение генералом.

Клан принимает только игроков 10+ уровня, поэтому скрипт проверяет уровень и,
если герой ещё слаб, выходит и ждёт следующего запуска.

Профили браузера здесь временные (два независимых входа), чтобы не мешать
работающим агентам.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def creds_path(env_name: str, win_default: str, cloud_name: str) -> Path:
    """Путь к файлу учётных данных: переменная окружения → облако → локальный путь."""
    raw = os.environ.get(env_name, "").strip()
    if raw:
        return Path(raw)
    candidate = Path("/opt/barbars-agent/credentials") / cloud_name
    if candidate.exists():
        return candidate
    return Path(win_default)


KEIS_CREDS = creds_path(
    "BARBARS_CREDS_KEIS", r"C:\Users\Богдан\Desktop\barbars-agentcredentials.txt", "keis.txt"
)
NEW_CREDS = creds_path(
    "BARBARS_CREDS_FIREWHITE",
    r"C:\Users\Богдан\Desktop\barbars-firewhite-credentials.txt",
    "firewhite.txt",
)
GUILD = "16675"
NEW_NICK = "fire white ii"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
RANKS = ["рядовой", "офицер", "генерал", "маршал", "лидер"]


LOG_FILE = ROOT / "logs" / "clan-auto.log"


def log(message: str) -> None:
    line = f"{datetime.now():%H:%M:%S} {message}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def open_ctx(pw, profile: Path):
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(profile), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )


def login(ctx, creds: Path) -> None:
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
    body = " ".join(page.inner_text("body").split())
    if "Вход для игроков" not in body:
        return
    raw = creds.read_text(encoding="utf-8-sig")
    lines = [l.strip().lstrip("\ufeff").strip() for l in raw.splitlines()]
    lines = [l for l in lines if l]
    user, password = lines[0], lines[1]
    page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
    page.fill("input[name='login']", user)
    page.fill("input[name='password']", password)
    page.click("input[type='submit']")
    page.wait_for_load_state("domcontentloaded", timeout=60_000)
    log(f"вошёл: {user}")


def hero_level(page) -> int:
    page.goto("https://barbars.ru/user", wait_until="domcontentloaded", timeout=60_000)
    body = " ".join(page.inner_text("body").split())
    # Над героем висит панель «новый предмет» («Штаны 1 ур, новый») — она ломает
    # наивный разбор, поэтому ищем строку героя «ник , N ур,» либо класс.
    match = re.search(r"(\d+)\s*ур,\s*(воин|медик)", body, re.IGNORECASE)
    if match:
        return int(match.group(1))
    idx = body.lower().find(NEW_NICK.lower())
    if idx >= 0:
        match = re.search(r"(\d+)\s*ур", body[idx:])
        if match:
            return int(match.group(1))
    match = re.search(r",\s*(\d+)\s*ур,", body)
    return int(match.group(1)) if match else 0


def main() -> int:
    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, ROOT / "profile-keis-clan")
        ctx_b = open_ctx(pw, ROOT / "profile-fw-clan")

        login(ctx_a, KEIS_CREDS)
        login(ctx_b, NEW_CREDS)

        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        level = hero_level(page_b)
        log(f"уровень героя: {level}")
        if level < 11:
            log("уровень ниже 11 — в клан пока нельзя, выходим")
            ctx_a.close()
            ctx_b.close()
            return 0

        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_a.goto("https://barbars.ru/users/search", wait_until="domcontentloaded", timeout=60_000)
        page_a.fill("input[name='name']", NEW_NICK, timeout=10_000)
        page_a.click("input[type='submit']")
        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
        link = page_a.query_selector(f"a:has-text('{NEW_NICK}')")
        if not link:
            log("герой не найден в поиске")
            ctx_a.close()
            ctx_b.close()
            return 1
        link.click()
        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
        invite = page_a.query_selector("a:has-text('Пригласить в клан')")
        if invite:
            invite.click()
            page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
            log(f"приглашение отправлено: {' '.join(page_a.inner_text('body').split())[:150]}")
        else:
            # приглашение, скорее всего, уже висит — идём принимать
            log("кнопки приглашения нет (приглашение, вероятно, уже отправлено)")

        # герой принимает приглашение
        for _ in range(6):
            page_b.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
            body = " ".join(page_b.inner_text("body").split())
            if re.search(r"приглашает тебя в клан|вступить|принять|приглашени", body, re.I):
                log(f"герой видит приглашение: {body[:200]}")
                accepted = False
                # сперва пробуем штатную ссылку «принять» (acceptLink)
                accept = page_b.query_selector("a[href*='acceptLink']")
                if accept:
                    accept.click()
                    page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                    log("нажато «принять» (acceptLink)")
                    accepted = True
                if not accepted:
                    for word in ("принять", "Вступить", "Принять", "Приглашение"):
                        btn = page_b.query_selector(f"a:has-text('{word}')")
                        if btn:
                            btn.click()
                            page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                            log(f"нажато «{word}»")
                            break
                break
            time.sleep(3)
        else:
            log("герой не увидел приглашение")

        page_b.goto(f"https://barbars.ru/guild/{GUILD}", wait_until="domcontentloaded", timeout=60_000)
        body_b = " ".join(page_b.inner_text("body").split())
        log(f"клан глазами героя: {body_b[:260]}")
        joined = NEW_NICK.lower() in body_b.lower() and "Участники" in body_b

        # лидер повышает до генерала
        if joined:
            for step in range(4):
                page_a.goto(f"https://barbars.ru/guild/{GUILD}", wait_until="domcontentloaded", timeout=60_000)
                page_a.click("a:has-text('Управление кланом')")
                page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                html = page_a.content()
                idx = html.find(NEW_NICK)
                if idx < 0:
                    log("героя нет в списке участников")
                    break
                # блок участника: от ближайшего <div> до следующего </div><div>
                start = html.rfind("<div>", 0, idx)
                end = html.find("<div>", idx)
                block = html[start:end if end > 0 else idx + 2000]
                m = re.search(r"<span>\s*(рядовой|офицер|генерал|маршал|лидер)\s*</span>", block)
                rank = m.group(1) if m else None
                log(f"текущий ранг: {rank}")
                if rank == "генерал":
                    log("ранг генерал получен")
                    break
                m = re.search(r'href="([^"]*promoteLink[^"]*)"', block)
                if not m:
                    log("кнопки повышения нет")
                    break
                page_a.goto(urljoin(page_a.url, m.group(1).replace("&amp;", "&")),
                            wait_until="domcontentloaded", timeout=60_000)
                time.sleep(1)
        else:
            log("герой пока не в клане")

        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
