"""Протокол рейда v3: оба в зале → оба «Я готов!» → keis жмёт «Начать бой!».

Проверяем главное: вступает ли в бой герой, который был готов в зале.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_raid_party import in_fight, login, open_ctx, room_html, who_is_here  # noqa: E402


def wait_open(page, label: str, timeout: int = 600) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        html = room_html(page)
        text = " ".join(page.inner_text("body").split())
        if "Вход закрыт" not in text and "Начать бой!" in text:
            print(f"[{label}] пещера открыта")
            return True
        m = re.search(r"Откроется через[:\s]*([\d:]+)", text)
        print(f"[{label}] пещера закрыта" + (f", откроется через {m.group(1)}" if m else ""))
        time.sleep(20)
    return False


def ready(page, label: str) -> None:
    try:
        page.click("a:has-text('Я готов!')", timeout=8000)
        print(f"[{label}] нажал «Я готов!»")
    except Exception as exc:
        print(f"[{label}] «Я готов!»: {exc}")
    time.sleep(3)


def main() -> int:
    a = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    b = sys.argv[2] if len(sys.argv) > 2 else "keis"
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, root / f"profile-party3-{a}")
        ctx_b = open_ctx(pw, root / f"profile-party3-{b}")
        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        login(ctx_a, a)
        login(ctx_b, b)

        wait_open(page_a, a)
        wait_open(page_b, b)

        # оба в зале
        room_html(page_a)
        room_html(page_b)
        print("[+] оба в зале")

        # оба готовы
        ready(page_a, a)
        ready(page_b, b)
        print("[A]", who_is_here(room_html(page_a)))
        print("[B]", who_is_here(room_html(page_b)))

        # старт
        try:
            page_b.click("a:has-text('Начать бой!')", timeout=8000)
            print(f"[{b}] нажал «Начать бой!»")
        except Exception as exc:
            print(f"[{b}] «Начать бой!»: {exc}")

        for i in range(18):
            time.sleep(10)
            state_a = in_fight(page_a)
            state_b = in_fight(page_b)
            print(f"[{i * 10:3}с] A: {state_a} | B: {state_b}")
            if "БОЙ" in state_a and "БОЙ" in state_b:
                print("   >>> ОБА В БОЮ")
                break
        (root / "tests" / "raw" / "party3-a.html").write_text(page_a.content(), encoding="utf-8")
        (root / "tests" / "raw" / "party3-b.html").write_text(page_b.content(), encoding="utf-8")
        print("A:", " ".join(page_a.inner_text("body").split())[:250])
        print("B:", " ".join(page_b.inner_text("body").split())[:250])
        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
