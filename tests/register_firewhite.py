"""Автоматическая регистрация аккаунта «Fire White» на barbars.ru.

Сервер открывает форму регистрации не всегда (воронка нового игрока), поэтому
скрипт терпеливо опрашивает игру и, как только форма появилась, заполняет её и
отправляет. Если потребуется captcha или подтверждение почты — останавливается и
пишет об этом в лог.

Запуск:  python tests\\register_firewhite.py
"""
from __future__ import annotations

import json
import random
import re
import secrets
import time
from datetime import datetime
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

NICK = "Fire White"
PASSWORD = "Fw" + secrets.token_urlsafe(12)
MAIL = f"firewhite{random.randint(1000, 9999)}@mailinator.com"

PATHS = [
    ["https://barbars.ru/start"],
    ["https://barbars.ru/guild/16675", "https://barbars.ru/registration"],
    ["https://barbars.ru/", "https://barbars.ru/registration"],
    ["https://barbars.ru/game/dungeons", "https://barbars.ru/registration"],
    ["https://barbars.ru/?channelId=35", "https://barbars.ru/registration"],
]


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def parse_form(html: str) -> tuple[str, dict[str, str], list[str]] | None:
    """Возвращает (action, hidden-поля, имена полей) формы регистрации."""
    if "registrationForm" not in html:
        return None
    action = re.search(r'<form[^>]*action="([^"]*)"[^>]*method="post"', html)
    if not action:
        return None
    hidden = {
        name: value
        for name, value in re.findall(
            r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html
        )
    }
    fields = re.findall(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', html)
    return action.group(1), hidden, fields


def field_options(html: str, name: str) -> list[tuple[str, str]]:
    block = re.search(rf"<select[^>]*name=\"{re.escape(name)}\"[^>]*>(.*?)</select>", html, re.S | re.I)
    if not block:
        return []
    out = []
    for opt in re.findall(r"<option[^>]*>", block.group(1), re.I):
        value = re.search(r'value="([^"]*)"', opt)
        text = " ".join(re.sub(r"<[^>]+>", " ", opt).split())
        out.append((value.group(1) if value else "", text))
    return out


def main() -> None:
    log(f"ник: {NICK} | пароль: {PASSWORD} | почта: {MAIL}")
    deadline = time.time() + 60 * 90
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
        html = ""
        action = ""
        for path in PATHS[attempt % len(PATHS)]:
            try:
                resp = session.get(path, timeout=25)
            except Exception as exc:  # noqa: BLE001
                log(f"[{attempt}] ошибка {path}: {exc}")
                continue
            html = resp.text
            parsed = parse_form(html)
            if parsed:
                action = parsed[0]
                break
            if "Долина варваров" in html:
                fight = re.search(r'href="([^"]*attackLink[^"]*)"', html)
                if fight:
                    from urllib.parse import urljoin

                    resp2 = session.get(urljoin(resp.url, fight.group(1)), timeout=25)
                    html = resp2.text
                    parsed = parse_form(html)
                    if parsed:
                        action = parsed[0]
                        break
        if not action:
            log(f"[{attempt}] формы нет (len={len(html)})")
            time.sleep(2 + random.random() * 2)
            continue

        log(f"[{attempt}] ФОРМА НАЙДЕНА! action={action}")
        (OUT / "registration-form.html").write_text(html, encoding="utf-8")
        _, hidden, fields = parse_form(html)
        log(f"поля: {fields}")
        for name in fields:
            opts = field_options(html, name)
            if opts:
                log(f"  {name}: {opts}")

        data = dict(hidden)
        data["login"] = NICK
        data["password"] = PASSWORD
        for name in fields:
            low = name.lower()
            if low in ("login", "password"):
                continue
            if "mail" in low or low in ("email", "e-mail"):
                data[name] = MAIL
            elif low == "sex":
                data[name] = "m"
            elif low == "side":
                data[name] = "1"
            elif low == "type":
                opts = field_options(html, name)
                pick = next((v for v, t in opts if "медик" in t.lower()), "")
                if not pick and opts:
                    pick = opts[0][0]
                data[name] = pick
            elif low in ("captcha", "code"):
                log("нужен captcha — регистрацию придётся завершить вручную")
                (ROOT / "credentials-firewhite.json").write_text(
                    json.dumps({"nick": NICK, "password": PASSWORD, "mail": MAIL}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return
        if "password" not in {k.lower() for k in data}:
            for name in fields:
                if "pass" in name.lower():
                    data[name] = PASSWORD

        target = "https://barbars.ru/" + action.lstrip("/")
        res = session.post(target, data=data, timeout=25, headers={"Referer": resp.url})
        log(f"ответ: {res.status_code} len={len(res.text)} url={res.url}")
        text = re.sub(r"<[^>]+>", " ", res.text)
        log("текст: " + " ".join(text.split())[:400])
        (OUT / "registration-result.html").write_text(res.text, encoding="utf-8")

        # сохраняем cookies сессии и учётные данные
        cookies = {c.name: c.value for c in session.cookies}
        (OUT / "registration-session.json").write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (ROOT / "credentials-firewhite.json").write_text(
            json.dumps({"nick": NICK, "password": PASSWORD, "mail": MAIL}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log("сохранены cookies и учётные данные")
        return
    log("форма так и не появилась")


if __name__ == "__main__":
    main()
