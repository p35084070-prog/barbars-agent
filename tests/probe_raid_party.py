"""Совместный бой: два героя в одном зале дракона.

Герой A (firewhite, воин) входит в зал и жмёт «Я готов!».
Герой B (keis, медик, ветеран клана) входит и жмёт «Начать бой!».
Проверяем: вступают ли оба в один бой (у A появляется «Бить дракона»/лечение,
у B видно обоих в «Кто здесь»).

Запуск: python tests\probe_raid_party.py [A] [B]
"""
from __future__ import annotations

import re
import shutil
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "tests" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

BASE = "https://barbars.ru"
DESKTOP = Path(r"C:\Users\Богдан\Desktop")
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ACCOUNTS = {
    "firewhite": "barbars-firewhite-credentials.txt",
    "keis": "barbars-agentcredentials.txt",
    "vagojan": "barbars-vagojan-credentials.txt",
}


def creds(name: str):
    f = DESKTOP / name
    if not f.exists():
        return None
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def open_ctx(pw, profile: Path):
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(profile), headless=True, user_agent=UA,
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
        locale="ru-RU",
    )


def login(ctx, who: str) -> None:
    data = creds(ACCOUNTS[who])
    if not data:
        raise SystemExit(f"нет учётных данных для {who}")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=60_000)
    page.fill("input[name='login']", data[0])
    page.fill("input[name='password']", data[1])
    page.click("input[type='submit']")
    page.wait_for_load_state("domcontentloaded", timeout=60_000)


def room_html(page) -> str:
    page.goto(f"{BASE}/game/dragonDungeon", wait_until="domcontentloaded", timeout=60_000)
    return page.content()


def who_is_here(html: str) -> str:
    idx = html.find("Кто здесь")
    counters = re.findall(r'icons/(blue_warrior|blue_healer)\.png"[^>]*>\s*<span>(\d+)</span>', html)
    cnt = ", ".join(f"{k}:{v}" for k, v in counters[:2])
    if idx < 0:
        return f"в зале: — (счётчики {cnt})"
    block = html[idx:idx + 1500]
    names = re.findall(r'user/id/\d+"><span>([^<]+)</span>', block)
    green = block.count("check_green")
    gray = block.count("check_gray")
    return f"в зале: {names} (готовых {green}, неготовых {gray}) | счётчики {cnt}"


def in_fight(page) -> str:
    body = " ".join(page.inner_text("body").split())
    if "Бить дракона" in body:
        return "БОЙ: можно бить дракона"
    if "Лечить союзников" in body:
        return "БОЙ: можно лечить союзников"
    if "Вход закрыт" in body:
        return "вход закрыт"
    if "Пустая пещера" in body:
        return "пещера пуста"
    return "вне боя"


def main() -> int:
    a = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    b = sys.argv[2] if len(sys.argv) > 2 else "keis"
    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, ROOT / f"profile-party-{a}")
        ctx_b = open_ctx(pw, ROOT / f"profile-party-{b}")
        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        login(ctx_a, a)
        login(ctx_b, b)

        # Герой A: в зал и «Я готов!»
        html = room_html(page_a)
        text = " ".join(page_a.inner_text("body").split())
        print(f"[{a}] зал: {text[:200]}")
        if "Вход закрыт" in text:
            print(f"[{a}] пещера закрыта — ждём открытия")
            for _ in range(30):
                time.sleep(20)
                html = room_html(page_a)
                text = " ".join(page_a.inner_text("body").split())
                if "Вход закрыт" not in text:
                    print(f"[{a}] пещера открылась")
                    break
        try:
            page_a.click("a:has-text('Я готов!')", timeout=8000)
            print(f"[{a}] нажал «Я готов!»")
        except Exception as exc:
            print(f"[{a}] «Я готов!»: {exc}")
        time.sleep(2)
        print(f"[{a}] зал: {who_is_here(room_html(page_a))}")

        # Герой B: в зал, ждёт, пока A будет в зале, потом «Начать бой!»
        time.sleep(15)
        html = room_html(page_b)
        text = " ".join(page_b.inner_text("body").split())
        print(f"[{b}] зал: {text[:200]}")
        print(f"[{b}] {who_is_here(html)}")
        html_a = room_html(page_a)
        print(f"[{a}] перед стартом: {who_is_here(html_a)}")
        try:
            page_b.click("a:has-text('Начать бой!')", timeout=8000)
            print(f"[{b}] нажал «Начать бой!»")
        except Exception as exc:
            print(f"[{b}] «Начать бой!»: {exc}")

        # Наблюдаем за обоими 2 минуты
        for i in range(12):
            time.sleep(10)
            state_a = in_fight(page_a)
            state_b = in_fight(page_b)
            print(f"[{i * 10:3}с] A: {state_a} | B: {state_b}")
            if "БОЙ" in state_a and "БОЙ" in state_b:
                print("   >>> Оба в бою!")
                time.sleep(2)
                (RAW / "party-a.html").write_text(page_a.content(), encoding="utf-8")
                (RAW / "party-b.html").write_text(page_b.content(), encoding="utf-8")
                break
        (RAW / "party-a.html").write_text(page_a.content(), encoding="utf-8")
        (RAW / "party-b.html").write_text(page_b.content(), encoding="utf-8")
        print("A:", " ".join(page_a.inner_text("body").split())[:300])
        print("B:", " ".join(page_b.inner_text("body").split())[:300])
        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
