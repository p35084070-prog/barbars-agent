"""Финальный тест рейда: оба готовы → keis стартует → firewhite заходит через
«Вернуться в бой» (/game/dungeons) и бьёт дракона.

Проверяем: входит ли второй герой в общий бой и наносит ли урон.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_raid_party import in_fight, login, open_ctx, who_is_here  # noqa: E402
from probe_raid_party3 import ready, wait_open  # noqa: E402


def dungeons_text(page) -> str:
    page.goto("https://barbars.ru/game/dungeons", wait_until="domcontentloaded", timeout=60_000)
    return " ".join(page.inner_text("body").split())


def main() -> int:
    a = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    b = sys.argv[2] if len(sys.argv) > 2 else "keis"
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, root / f"profile-party4-{a}")
        ctx_b = open_ctx(pw, root / f"profile-party4-{b}")
        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        login(ctx_a, a)
        login(ctx_b, b)

        wait_open(page_a, a)
        wait_open(page_b, b)

        page_a.goto("https://barbars.ru/game/dragonDungeon", wait_until="domcontentloaded", timeout=60_000)
        page_b.goto("https://barbars.ru/game/dragonDungeon", wait_until="domcontentloaded", timeout=60_000)
        print("[+] оба в зале")
        ready(page_a, a)
        ready(page_b, b)
        print("[A]", who_is_here(page_a.content()))
        print("[B]", who_is_here(page_b.content()))

        page_b.click("a:has-text('Начать бой!')", timeout=8000)
        print(f"[{b}] нажал «Начать бой!»")
        time.sleep(4)

        # второй герой идёт в бой через «Вернуться в бой»
        text = dungeons_text(page_a)
        print(f"[{a}] пещеры: {text[:200]}")
        if "Вернуться в бой" in text:
            page_a.click("a:has-text('Вернуться в бой')", timeout=8000)
            page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
            time.sleep(2)
            body = " ".join(page_a.inner_text("body").split())
            print(f"[{a}] в бою: {body[:300]}")
            for i in range(4):
                link = page_a.query_selector("a:has-text('Бить дракона')")
                if not link:
                    print(f"[{a}] кнопки удара нет")
                    break
                link.click()
                page_a.wait_for_load_state("domcontentloaded", timeout=60_000)
                time.sleep(1.5)
                body = " ".join(page_a.inner_text("body").split())
                m = re.search(r"Ты ударил дракона на ([^\s]+(?:\s+[^\s]+)?)", body)
                hp = re.search(r"Мифический дракон\s+(\d+)%", body)
                print(f"[{a}] удар {i + 1}: урон={m.group(1) if m else '?'} HP босса={hp.group(1) if hp else '?'}%")
        else:
            print(f"[{a}] «Вернуться в бой» не найдено — значит, в бой не попал")

        (root / "tests" / "raw" / "party4-a.html").write_text(page_a.content(), encoding="utf-8")
        (root / "tests" / "raw" / "party4-b.html").write_text(page_b.content(), encoding="utf-8")
        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
