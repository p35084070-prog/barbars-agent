"""Охотник за формой регистрации barbars.ru.

Сервер отдаёт форму только в «воронке» нового игрока (страница «Долина варваров»
или гостевая страница с кнопкой «Регистрация»). Перебираем попытки с разными
адресами и сохраняем найденную форму вместе с cookies сессии.
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

PATHS = [
    ["https://barbars.ru/start"],
    ["https://barbars.ru/guild/16675", "https://barbars.ru/registration"],
    ["https://barbars.ru/", "https://barbars.ru/registration"],
    ["https://barbars.ru/user", "https://barbars.ru/registration"],
    ["https://barbars.ru/game/dungeons", "https://barbars.ru/registration"],
]


def has_form(html: str) -> bool:
    return "registrationForm" in html


def has_valley(html: str) -> bool:
    return "Долина варваров" in html or "attackLink" in html


def main() -> None:
    deadline = time.time() + 60 * 25
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
        html = ""
        for path in PATHS[attempt % len(PATHS)]:
            try:
                resp = session.get(path, timeout=25)
            except Exception as exc:  # noqa: BLE001
                print(f"[{attempt}] ошибка {path}: {exc}", flush=True)
                continue
            html = resp.text
            if has_form(html):
                break
            if has_valley(html):
                fight = re.search(r'href="([^"]*attackLink[^"]*)"', html)
                if fight:
                    from urllib.parse import urljoin

                    resp2 = session.get(urljoin(resp.url, fight.group(1)), timeout=25)
                    html = resp2.text
                break
        if has_form(html):
            (OUT / "registration-form.html").write_text(html, encoding="utf-8")
            cookies = {c.name: c.value for c in session.cookies}
            (OUT / "registration-session.json").write_text(
                json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[{attempt}] ФОРМА НАЙДЕНА, cookies сохранены", flush=True)
            for tag in re.findall(r"<(?:input|select)[^>]*>", html, re.IGNORECASE):
                print("   ", " ".join(tag.split()), flush=True)
            for opt in re.findall(r"<option[^>]*>", html, re.IGNORECASE):
                print("    option:", " ".join(opt.split()), flush=True)
            return
        print(f"[{attempt}] формы нет (len={len(html)})", flush=True)
        time.sleep(1.0 + random.random())
    print("форма не найдена за отведённое время", flush=True)


if __name__ == "__main__":
    main()
