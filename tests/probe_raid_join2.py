"""Как вступить в уже начатый общий бой с драконом.

keis (ветеран) жмёт «Начать бой!», а firewhite перебирает способы входа:
  1) обновить страницу зала,
  2) «Вернуться в бой» на /game/dungeons,
  3) нажать «Начать бой!» самому,
  4) снова обновить зал.
Каждый шаг логируется, чтобы понять, какой путь работает.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_raid_party import login, open_ctx, room_html, who_is_here  # noqa: E402
from probe_raid_party3 import ready, wait_open  # noqa: E402

BASE = "https://barbars.ru"
ROOT = Path(__file__).resolve().parents[1]


def state(page) -> str:
    text = " ".join(page.inner_text("body").split())
    if "Бить дракона" in text:
        return "БОЙ: можно бить дракона"
    if "Лечить союзников" in text:
        return "БОЙ: можно лечить"
    if "Покинуть бой" in text:
        return "бой есть (панель), действий нет"
    if "не можешь принять участие" in text:
        return "не допущен к бою"
    if "Начать бой!" in text:
        return "зал (кнопка старта на месте)"
    if "Вход закрыт" in text:
        return "зал закрыт"
    return "???"


def show(page, label: str) -> str:
    st = state(page)
    print(f"    [{label}] {st}")
    return st


def try_join(page, label: str) -> str:
    """Перебор способов входа. Возвращает итоговое состояние."""
    print(f"  шаг 1: обновить зал ({label})")
    room_html(page)
    st = show(page, label)
    if st.startswith("БОЙ"):
        return st

    print(f"  шаг 2: /game/dungeons → «Вернуться в бой» ({label})")
    page.goto(f"{BASE}/game/dungeons", wait_until="domcontentloaded", timeout=60_000)
    text = " ".join(page.inner_text("body").split())
    if "Вернуться в бой" in text:
        page.click("a:has-text('Вернуться в бой')", timeout=8000)
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
        time.sleep(2)
        st = show(page, label)
        if st.startswith("БОЙ"):
            return st
    else:
        print(f"    [{label}] «Вернуться в бой» нет")

    print(f"  шаг 3: самому нажать «Начать бой!» ({label})")
    room_html(page)
    try:
        page.click("a:has-text('Начать бой!')", timeout=8000)
        page.wait_for_load_state("domcontentloaded", timeout=60_000)
        time.sleep(2)
        print("    нажали")
    except Exception as exc:
        print(f"    не получилось: {exc}")
    st = show(page, label)
    if st.startswith("БОЙ"):
        return st

    print(f"  шаг 4: снова обновить зал ({label})")
    room_html(page)
    st = show(page, label)
    return st


def main() -> int:
    a = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    b = sys.argv[2] if len(sys.argv) > 2 else "keis"
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, ROOT / f"profile-join2-{a}")
        ctx_b = open_ctx(pw, ROOT / f"profile-join2-{b}")
        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        login(ctx_a, a)
        login(ctx_b, b)

        wait_open(page_a, a)
        wait_open(page_b, b)

        room_html(page_a)
        room_html(page_b)
        print("[+] оба в зале")
        ready(page_a, a)
        ready(page_b, b)
        print("[A]", who_is_here(room_html(page_a)))
        print("[B]", who_is_here(room_html(page_b)))

        try:
            page_b.click("a:has-text('Начать бой!')", timeout=8000)
            print(f"[{b}] нажал «Начать бой!»")
        except Exception as exc:
            print(f"[{b}] «Начать бой!»: {exc}")
        time.sleep(3)
        print(f"[{b}] сразу после старта: {state(page_b)}")

        for round_no in range(4):
            print(f"--- раунд {round_no + 1} ---")
            st = try_join(page_a, a)
            print(f"  [{b}] {state(page_b)}")
            if st.startswith("БОЙ"):
                print("[+] ВОШЛИ В БОЙ!")
                break
            time.sleep(10)

        (ROOT / "tests" / "raw" / "join2-a.html").write_text(page_a.content(), encoding="utf-8")
        (ROOT / "tests" / "raw" / "join2-b.html").write_text(page_b.content(), encoding="utf-8")
        print("A:", " ".join(page_a.inner_text("body").split())[:300])
        print("B:", " ".join(page_b.inner_text("body").split())[:300])
        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
