"""Усталость героя: сколько, чем снимается, какая справка.

Проверяем на keis и firewhite: значение усталости, цену «Снять усталость»
(золото или серебро) и ссылку на справку рядом с этим блоком.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from barbars.driver import Game  # noqa: E402
from game_state import DESKTOP  # noqa: E402

BASE = "https://barbars.ru"
ACC = {
    "keis": "barbars-agentcredentials.txt",
    "firewhite": "barbars-firewhite-credentials.txt",
}


def creds(name: str):
    f = DESKTOP / name
    if not f.exists():
        return None
    lines = [l.strip().lstrip("\ufeff") for l in f.read_text(encoding="utf-8-sig").splitlines()]
    return [l for l in lines if l][:2]


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    data = creds(ACC[who])
    if not data:
        print(f"нет учётных данных для {who}")
        return 1
    user, password = data
    g = Game({"base_url": BASE, "profile_dir": f"profile-fatigue-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / ACC[who])},
              "humanize": {"enabled": False}}, f"profile-fatigue-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        for url in ("/user/tire",):
            g.goto(BASE + url)
            html = g.p.content()
            text = " ".join(g.body_text().split())
            i = text.lower().find("сталост")
            print(f"--- {url}: {'есть усталость' if i >= 0 else 'нет'} (длина {len(text)})")
            if i < 0:
                continue
            print("   контекст:", text[max(0, i - 100):i + 320])
            j = html.find("сталост")
            if j < 0:
                j = html.find("Усталост")
            chunk = re.sub(r"\s+", " ", html[max(0, j - 1500):j + 2500])
            print("   иконки монет:", re.findall(r'src="(/images/icons/money[^"]*)"', chunk))
            print("   ссылки:", [h for h in re.findall(r'href="([^"]+)"', chunk)
                                if "help" in h or "gold" in h or "tired" in h])
            print("   фрагмент:", chunk[:1200])
            after = re.sub(r"\s+", " ", html[j:j + 1200])
            print("   ПОСЛЕ БЛОКА:", after[:1000])
            before = re.sub(r"\s+", " ", html[max(0, j - 500):j + 60])
            print("   ДО БЛОКА:", before[-500:])
            print("   все ссылки страницы:", [h for h in re.findall(r'href="([^"]+)"', html)
                                             if "user/" in h or "help" in h][:12])
            print("   title-подсказки:", re.findall(r'title="([^"]{3,120})"', chunk))

        # Шапка героя: HP, энергия, золото, серебро — и есть ли «Покинуть бой».
        g.goto(BASE + "/")
        html = g.p.content()
        text = " ".join(g.body_text().split())
        head = re.search(
            r"(\d[\d\s]*)\s*/\s*(\d[\d\s]*).*?золото\s*=\s*(\d+)\s+серебро\s*=\s*(\d+)", text)
        print()
        print(f"===== {who}: шапка =====")
        print("начало текста:", text[:260])
        print("Покинуть бой" in text, "| Вернуться в бой" in text)
        m = re.search(r"золото\s*=\s*(\d+)\s+серебро\s*=\s*(\d+)", text)
        if m:
            print("золото/серебро:", m.group(1), "/", m.group(2))

        # кусок HTML вокруг «Усталость» — там и цена, и возможная ссылка в справку
        j = html.find("Усталость")
        if j >= 0:
            chunk = html[max(0, j - 1200):j + 2500]
            chunk = re.sub(r"\s+", " ", chunk)
            print()
            print("HTML:", chunk[:2200])
            print()
            print("ссылки рядом:", re.findall(r'href="([^"]+)"', chunk))
            print("иконки монет:", re.findall(r'src="(/images/icons/[^"]+)"', chunk))
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
