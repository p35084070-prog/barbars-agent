"""Регистрация «Fire White» на barbars.ru через прокси-мост (смена исходящего IP).

Прямой IP компьютера сервер больше не пускает в воронку нового игрока (отдаёт
заставку), но через локальный прокси 127.0.0.1:10809 воронка открывается:
/start -> «Долина варваров» -> «Сразиться!» -> форма регистрации.
"""
from __future__ import annotations

import json
import random
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
PROXY = "http://127.0.0.1:10809"
PROXIES = {"http": PROXY, "https": PROXY}

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

NICK = "Fire White"
PASSWORD = "Fw" + secrets.token_urlsafe(12)


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    session.proxies.update(PROXIES)
    return session


def find_form(html: str) -> tuple[str, dict[str, str], list[str]] | None:
    if "registrationForm" not in html:
        return None
    action = re.search(r'<form[^>]*action="([^"]+)"', html)
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


def select_options(html: str, name: str) -> list[tuple[str, str]]:
    block = re.search(rf"<select[^>]*name=\"{re.escape(name)}\"[^>]*>(.*?)</select>", html, re.S | re.I)
    if not block:
        return []
    out = []
    for opt in re.findall(r"<option[^>]*>", block.group(1), re.I):
        value = re.search(r'value="([^"]*)"', opt)
        text = " ".join(re.sub(r"<[^>]+>", " ", opt).split())
        out.append((value.group(1) if value else "", text))
    return out


def get_registration_form(session: requests.Session) -> tuple[str, str, list[str]] | None:
    """Проходит воронку и возвращает (html, action, поля)."""
    resp = session.get("https://barbars.ru/start", timeout=30)
    if "Долина варваров" not in resp.text:
        return None
    fight = re.search(r'href="([^"]*attackLink[^"]*)"', resp.text)
    if not fight:
        return None
    resp2 = session.get(urljoin(resp.url, fight.group(1)), timeout=30, headers={"Referer": resp.url})
    parsed = find_form(resp2.text)
    if not parsed:
        return None
    return resp2.text, parsed[0], parsed[2]


def main() -> None:
    log(f"ник={NICK} пароль={PASSWORD} прокси={PROXY}")
    html = action = fields = None
    session = new_session()
    for attempt in range(1, 31):
        try:
            result = get_registration_form(session)
        except Exception as exc:  # noqa: BLE001
            log(f"[{attempt}] ошибка запроса: {exc}")
            session = new_session()
            time.sleep(2)
            continue
        if result:
            html, action, fields = result
            log(f"[{attempt}] ФОРМА НАЙДЕНА: action={action}")
            break
        log(f"[{attempt}] воронка не открылась (прокси сменил IP?)")
        session = new_session()
        time.sleep(2 + random.random() * 2)

    if not html:
        log("ФОРМУ НЕ УДАЛОСЬ ПОЛУЧИТЬ")
        return

    (OUT / "registration-form.html").write_text(html, encoding="utf-8")
    _, hidden, fields = find_form(html)
    log(f"поля: {fields}")
    for name in fields:
        opts = select_options(html, name)
        if opts:
            log(f"  {name}: {opts}")

    data = dict(hidden)
    data["login"] = NICK
    for name in fields:
        low = name.lower()
        if low == "login":
            continue
        if "pass" in low:
            data[name] = PASSWORD
        elif "mail" in low or low in ("email", "e-mail"):
            data[name] = f"firewhite{random.randint(1000, 9999)}@mailinator.com"
        elif low == "sex":
            data[name] = "m"
        elif low == "side":
            data[name] = "1"
        elif low == "type":
            opts = select_options(html, name)
            pick = next((v for v, t in opts if "медик" in t.lower()), "")
            if not pick and opts:
                pick = opts[0][0]
            data[name] = pick
        elif low in ("captcha", "code", "verify"):
            log("требуется captcha — регистрацию придётся завершить вручную")
            return

    target = "https://barbars.ru/" + action.lstrip("/")
    log(f"отправляю форму на {target} :: {list(data)}")
    res = session.post(target, data=data, timeout=30, headers={"Referer": "https://barbars.ru/registration"})
    log(f"ответ: {res.status_code} len={len(res.text)} url={res.url}")
    text = re.sub(r"<[^>]+>", " ", res.text)
    log("текст: " + " ".join(text.split())[:500])
    (OUT / "registration-result.html").write_text(res.text, encoding="utf-8")

    cookies = {c.name: c.value for c in session.cookies}
    (OUT / "registration-session.json").write_text(
        json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "credentials-firewhite.json").write_text(
        json.dumps({"nick": NICK, "password": PASSWORD}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log("сохранены cookies сессии и учётные данные")


if __name__ == "__main__":
    main()
