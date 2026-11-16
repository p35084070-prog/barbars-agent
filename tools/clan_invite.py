"""Приглашение героя в клан и его вступление.

Две сессии: пригласитель (обычно keis — лидер «Слепых ТИТАНОВ») и сам герой.
Инвайтер ищет героя через /users/search и жмёт «Пригласить в клан», герой
принимает приглашение (acceptLink). Креды читаются из файлов (ник/пароль/пароль),
в лог не печатаются.

Запуск:
    python tools\\clan_invite.py --inviter-creds <file> --target-creds <file> \
        --target-nick "Steel Blue ii" --guild-id 16675
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def log(message: str) -> None:
    print(message, flush=True)


def open_ctx(pw, profile: Path):
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(profile), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )


def login(ctx, creds: Path) -> bool:
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
    body = " ".join(page.inner_text("body").split())
    if "Вход для игроков" not in body:
        return True
    raw = creds.read_text(encoding="utf-8-sig")
    lines = [l.strip().lstrip("\ufeff").strip() for l in raw.splitlines()]
    lines = [l for l in lines if l]
    user, password = lines[0], lines[1]
    page.goto("https://barbars.ru/login", wait_until="domcontentloaded", timeout=60_000)
    page.fill("input[name='login']", user)
    page.fill("input[name='password']", password)
    page.click("input[type='submit']")
    page.wait_for_load_state("domcontentloaded", timeout=60_000)
    body = " ".join(page.inner_text("body").split())
    ok = "Неверный ник или пароль" not in body and "Вход для игроков" not in body
    log(f"вход: {'ок' if ok else 'НЕ УДАЛСЯ'} (ник {user})")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inviter-creds", required=True)
    ap.add_argument("--target-creds", required=True)
    ap.add_argument("--target-nick", required=True)
    ap.add_argument("--guild-id", required=True)
    ap.add_argument("--wait-sec", type=int, default=90)
    args = ap.parse_args()

    with sync_playwright() as pw:
        with tempfile.TemporaryDirectory(prefix="inviter-") as t1:
            with tempfile.TemporaryDirectory(prefix="target-") as t2:
                ctx_a = open_ctx(pw, Path(t1))
                ctx_b = open_ctx(pw, Path(t2))
                try:
                    if not login(ctx_a, Path(args.inviter_creds)):
                        return 2
                    if not login(ctx_b, Path(args.target_creds)):
                        return 2

                    page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
                    page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()

                    # 1) инвайтер ищет героя и приглашает
                    page_a.goto("https://barbars.ru/users/search", wait_until="domcontentloaded", timeout=60_000)
                    page_a.fill("input[name='name']", args.target_nick, timeout=15_000)
                    page_a.click("input[type='submit']")
                    page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                    link = page_a.query_selector(f"a:has-text('{args.target_nick}')")
                    if not link:
                        log("герой не найден в поиске")
                        return 3
                    link.click()
                    page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                    invite = page_a.query_selector("a:has-text('Пригласить в клан')")
                    if invite:
                        invite.click()
                        page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                        log("приглашение отправлено: " + " ".join(page_a.inner_text("body").split())[:160])
                    else:
                        log("кнопки «Пригласить в клан» нет — приглашение, вероятно, уже висит")

                    # 2) герой принимает приглашение
                    deadline = time.time() + args.wait_sec
                    accepted = False
                    while time.time() < deadline and not accepted:
                        page_b.goto("https://barbars.ru/", wait_until="domcontentloaded", timeout=60_000)
                        body = " ".join(page_b.inner_text("body").split())
                        if re.search(r"приглашает тебя в клан|вступить в клан|принять приглашение", body, re.I):
                            log("герой видит приглашение")
                            accept = page_b.query_selector("a[href*='acceptLink']")
                            if accept:
                                accept.click()
                                page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                                log("нажато «принять»")
                                accepted = True
                                break
                            for word in ("принять", "Вступить", "Принять"):
                                btn = page_b.query_selector(f"a:has-text('{word}')")
                                if btn:
                                    btn.click()
                                    page_b.wait_for_load_state("domcontentloaded", timeout=60_000)
                                    log(f"нажато «{word}»")
                                    accepted = True
                                    break
                        time.sleep(4)
                    if not accepted:
                        log("герой не увидел приглашение за отведённое время")

                    # 3) проверка состава клана
                    page_b.goto(f"https://barbars.ru/guild/{args.guild_id}", wait_until="domcontentloaded", timeout=60_000)
                    body_b = " ".join(page_b.inner_text("body").split())
                    joined = args.target_nick.lower() in body_b.lower() and "Участники" in body_b
                    log(f"клан глазами героя: {'ГЕРОЙ В КЛАНЕ' if joined else 'героя в клане нет'}")
                    log(body_b[:300])
                    return 0 if joined else 4
                finally:
                    ctx_a.close()
                    ctx_b.close()


if __name__ == "__main__":
    raise SystemExit(main())
