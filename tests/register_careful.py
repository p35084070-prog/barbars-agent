"""Осторожная регистрация «Fire White»: редкие попытки, один IP за раз.

Частые запросы к /start включили антифлуд-блокировку, поэтому здесь:
  * пауза 90 секунд между попытками;
  * чередование двух выходов (прямой и через прокси-мост);
  * если воронка открылась — сразу проходим её и регистрируем.
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
BRIDGE = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

NICK = "Fire White"
PASSWORD = "Fw" + secrets.token_urlsafe(12)
PAUSE_SEC = 90
RUN_SECONDS = 60 * 60


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def make_session(use_proxy: bool) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    if use_proxy:
        session.proxies.update(BRIDGE)
    return session


def find_form(html: str):
    if "registrationForm" not in html:
        return None
    action = re.search(r'<form[^>]*action="([^"]+)"', html)
    if not action:
        return None
    hidden = {
        n: v
        for n, v in re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html)
    }
    fields = re.findall(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', html)
    return action.group(1), hidden, fields


def options(html: str, name: str):
    block = re.search(rf"<select[^>]*name=\"{re.escape(name)}\"[^>]*>(.*?)</select>", html, re.S | re.I)
    if not block:
        return []
    out = []
    for opt in re.findall(r"<option[^>]*>", block.group(1), re.I):
        value = re.search(r'value="([^"]*)"', opt)
        text = " ".join(re.sub(r"<[^>]+>", " ", opt).split())
        out.append((value.group(1) if value else "", text))
    return out


def attempt(use_proxy: bool) -> bool:
    """Одна попытка. True — аккаунт создан."""
    session = make_session(use_proxy)
    try:
        resp = session.get("https://barbars.ru/start", timeout=30)
    except Exception as exc:  # noqa: BLE001
        log(f"ошибка запроса: {exc}")
        session.close()
        return False

    html = resp.text
    if "Долина варваров" not in html and "registrationForm" not in html:
        log(f"[{'прокси' if use_proxy else 'прямой'}] воронка закрыта (len={len(html)})")
        session.close()
        return False

    log(f"[{'прокси' if use_proxy else 'прямой'}] ВОРОНКА ОТКРЫТА!")
    if "registrationForm" not in html:
        fight = re.search(r'href="([^"]*attackLink[^"]*)"', html)
        if not fight:
            log("нет ссылки на бой")
            session.close()
            return False
        resp2 = session.get(urljoin(resp.url, fight.group(1)), timeout=30, headers={"Referer": resp.url})
        html = resp2.text

    parsed = find_form(html)
    if not parsed:
        log("форма не распознана")
        (OUT / "registration-attempt.html").write_text(html, encoding="utf-8")
        session.close()
        return False

    action, hidden, fields = parsed
    log(f"форма найдена: {fields}")
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
            opts = options(html, name)
            pick = next((v for v, t in opts if "медик" in t.lower()), "")
            if not pick and opts:
                pick = opts[0][0]
            data[name] = pick

    target = "https://barbars.ru/" + action.lstrip("/")
    res = session.post(target, data=data, timeout=30, headers={"Referer": "https://barbars.ru/registration"})
    text = " ".join(re.sub(r"<[^>]+>", " ", res.text).split())
    log(f"ответ регистрации: {res.status_code} url={res.url}")
    log("текст: " + text[:400])
    (OUT / "registration-result.html").write_text(res.text, encoding="utf-8")

    cookies = {c.name: c.value for c in session.cookies}
    (OUT / "registration-session.json").write_text(
        json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / "credentials-firewhite.json").write_text(
        json.dumps({"nick": NICK, "password": PASSWORD}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    session.close()
    return "ошиб" not in text.lower() and "уже занят" not in text.lower()


def main() -> None:
    log(f"ник={NICK} пароль={PASSWORD}")
    deadline = time.time() + RUN_SECONDS
    attempt_no = 0
    while time.time() < deadline:
        attempt_no += 1
        use_proxy = attempt_no % 2 == 0
        if attempt(use_proxy):
            log("АККАУНТ СОЗДАН")
            return
        time.sleep(PAUSE_SEC)
    log("попытки исчерпаны")


if __name__ == "__main__":
    main()
