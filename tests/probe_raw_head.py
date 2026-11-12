"""Сырой HTML шапки и страницы мастерства — чтобы разобрать иконки ресурсов."""
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


def main() -> int:
    who = sys.argv[1] if len(sys.argv) > 1 else "keis"
    data = creds(ACC[who])
    if not data:
        print(f"нет учётных данных для {who}")
        return 1
    user, password = data
    OUT.mkdir(parents=True, exist_ok=True)
    g = Game({"base_url": BASE, "profile_dir": f"profile-raw-{who}", "headless": True,
              "auth": {"credentials_file": str(DESKTOP / ACC[who])},
              "humanize": {"enabled": False}}, f"profile-raw-{who}")
    g.start()
    try:
        g.goto(f"{BASE}/login")
        g.p.fill("input[name='login']", user, timeout=8000)
        g.p.fill("input[name='password']", password, timeout=8000)
        g.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
        g.p.wait_for_load_state("domcontentloaded", timeout=20000)
        assert g.is_authenticated(), "не удалось войти"

        g.goto(BASE + "/")
        html = g.p.content()
        (OUT / f"head-{who}.html").write_text(html, encoding="utf-8")
        print("иконки в шапке:", sorted(set(re.findall(r'icons/([\w.]+)\.png', html)))[:40])
        # верхние 1500 символов видимого текста
        print("текст:", " ".join(g.body_text().split())[:200])

        g.goto(BASE + "/user/master")
        html = g.p.content()
        (OUT / f"master-{who}.html").write_text(html, encoding="utf-8")
        print()
        print("иконки на /user/master:", sorted(set(re.findall(r'icons/([\w.]+)\.png', html))))
        i = html.find("moreParamsPanel")
        print("moreParamsPanel найден:", i >= 0)
        print("фрагмент:", re.sub(r"\s+", " ", html[max(0, i - 300):i + 1500])[:1600])
    finally:
        try:
            g.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
