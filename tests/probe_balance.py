"""Баланс ресурсов героя: железо, мифрил, серебро, золото, бутылки.

Страница «Мой герой» (/user) — там видны иконочные счётчики ресурсов.
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
OUT = Path(__file__).resolve().parent / "raw"
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


def counters(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for icon, num in re.findall(
            r'icons/([\w]+)\.png[^>]*>\s*(?:<[^>]+>\s*)*<span[^>]*>([\d.,]+[KkMm]?)</span>', html):
        out.setdefault(icon, num)
    for icon, num in re.findall(
            r'<span[^>]*>([\d.,]+[KkMm]?)</span>\s*</[^>]+>\s*<img[^>]*icons/([\w]+)\.png', html):
        out.setdefault(icon, num)
    return out


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    data = creds(ACC[who])
    if not data:
        print(f"нет учётных данных для {who}")
        return 1
    user, password = data
    OUT.mkdir(parents=True, exist_ok=True)
    g = Game({"base_url": BASE, "profile_dir": f"profile-res2-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / ACC[who])},
              "humanize": {"enabled": False}}, f"profile-res2-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        for url in ("/user", "/user/master"):
            g.goto(BASE + url)
            html = g.p.content()
            (OUT / f"{url.strip('/').replace('/', '-')}-{who}.html").write_text(html, encoding="utf-8")
            print(f"--- {url} ---")
            print("  счётчики:", counters(html))
            text = " ".join(g.body_text().split())
            for kw in ("желез", "мифрил", "серебр", "золот"):
                i = text.lower().find(kw)
                if i >= 0:
                    print(f"  {kw}: ...{text[max(0, i - 60):i + 80]}")
            if url == "/user/master":
                i = html.find("upgradeLink")
                print("  цена мастерства (фрагмент):",
                      re.sub(r"\s+", " ", html[max(0, i - 200):i + 700])[:800])
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
