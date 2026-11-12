"""Протокол рейда v2: сначала все в зале, потом все «Я готов!», потом «Начать бой!».

Шаги:
  1. Оба входят в зал и ждут, пока каждый увидит обоих в «Кто здесь».
  2. Оба жмут «Я готов!».
  3. Проверяем, что у обоих видно «готовых 2».
  4. keis жмёт «Начать бой!».
  5. Наблюдаем: вступили ли оба в бой.

Запуск: python tests\probe_raid_party2.py [A] [B]
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_raid_party import ACCOUNTS, creds, in_fight, login, open_ctx, room_html, who_is_here  # noqa: E402


def wait_open(page, label: str, timeout: int = 420) -> bool:
    """Ждём, пока пещера откроется («Начать бой!» есть, «Вход закрыт» нет)."""
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


def wait_party(page, label: str, need: int, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        html = room_html(page)
        names = re.findall(r'user/id/\d+"><span>([^<]+)</span>', html[html.find("Кто здесь"):][:1500])
        print(f"[{label}] в зале: {names}")
        if len(names) >= need:
            return True
        time.sleep(10)
    return False


def main() -> int:
    a = sys.argv[1] if len(sys.argv) > 1 else "firewhite"
    b = sys.argv[2] if len(sys.argv) > 2 else "keis"
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as pw:
        ctx_a = open_ctx(pw, root / f"profile-party2-{a}")
        ctx_b = open_ctx(pw, root / f"profile-party2-{b}")
        page_a = ctx_a.pages[0] if ctx_a.pages else ctx_a.new_page()
        page_b = ctx_b.pages[0] if ctx_b.pages else ctx_b.new_page()
        login(ctx_a, a)
        login(ctx_b, b)

        # 0. ждём открытия пещеры
        wait_open(page_a, a)
        wait_open(page_b, b)

        # 1. оба входят в зал
        room_html(page_a)
        room_html(page_b)
        print("[+] оба вошли в зал")

        # 2. ждём, пока каждый увидит обоих
        ok_a = wait_party(page_a, a, 2)
        ok_b = wait_party(page_b, b, 2)
        print(f"[+] видят друг друга: A={ok_a} B={ok_b}")

        # 3. оба жмут «Я готов!»
        for page, label in ((page_a, a), (page_b, b)):
            try:
                page.click("a:has-text('Я готов!')", timeout=8000)
                print(f"[{label}] нажал «Я готов!»")
            except Exception as exc:
                print(f"[{label}] «Я готов!»: {exc}")
            time.sleep(2)

        for page, label in ((page_a, a), (page_b, b)):
            html = room_html(page)
            print(f"[{label}] {who_is_here(html)}")

        # 4. keis начинает бой
        try:
            page_b.click("a:has-text('Начать бой!')", timeout=8000)
            print(f"[{b}] нажал «Начать бой!»")
        except Exception as exc:
            print(f"[{b}] «Начать бой!»: {exc}")

        # 5. наблюдаем
        for i in range(18):
            time.sleep(10)
            state_a = in_fight(page_a)
            state_b = in_fight(page_b)
            print(f"[{i * 10:3}с] A: {state_a} | B: {state_b}")
            if "БОЙ" in state_a and "БОЙ" in state_b:
                print("   >>> ОБА В БОЮ!")
                break
        (root / "tests" / "raw" / "party2-a.html").write_text(page_a.content(), encoding="utf-8")
        (root / "tests" / "raw" / "party2-b.html").write_text(page_b.content(), encoding="utf-8")
        print("A:", " ".join(page_a.inner_text("body").split())[:250])
        print("B:", " ".join(page_b.inner_text("body").split())[:250])
        ctx_a.close()
        ctx_b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
