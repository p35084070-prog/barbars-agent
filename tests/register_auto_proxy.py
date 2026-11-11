"""Ищет прокси и сразу регистрирует «Fire White», как только воронка открылась.

Публичные прокси живут секунды, поэтому сканирование и регистрация идут в одном
процессе: нашёл рабочий IP → прошёл воронку → заполнил форму → отправил.
"""
from __future__ import annotations

import json
import random
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
]

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

NICK = "Fire White"
PASSWORD = "Fw" + secrets.token_urlsafe(12)
DONE = threading.Event()
RESULT: dict[str, object] = {}


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


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


def register(session: requests.Session, html: str) -> None:
    """Проходит воронку и отправляет форму регистрации."""
    if "registrationForm" not in html:
        # после «долины» форма лежит на /registration в этой же сессии
        try:
            reg = session.get(
                "https://barbars.ru/registration",
                timeout=30,
                headers={"Referer": "https://barbars.ru/start"},
            )
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка запроса /registration: {exc}")
            reg = None
        if reg is not None and "registrationForm" in reg.text:
            html = reg.text
        else:
            fight = re.search(r'href="([^"]*attackLink[^"]*)"', html)
            if not fight:
                log("в воронке нет ссылки на бой")
                return
            resp2 = session.get(urljoin("https://barbars.ru/start", fight.group(1)), timeout=30,
                                headers={"Referer": "https://barbars.ru/start"})
            html = resp2.text

    parsed = find_form(html)
    if not parsed:
        (OUT / "registration-attempt.html").write_text(html, encoding="utf-8")
        log("форма не распознана")
        return
    action, hidden, fields = parsed
    log(f"ФОРМА: поля={fields}")
    for name in fields:
        opts = options(html, name)
        if opts:
            log(f"   {name}: {opts}")

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
    try:
        res = session.post(target, data=data, timeout=30,
                           headers={"Referer": "https://barbars.ru/registration"})
    except Exception as exc:  # noqa: BLE001
        log(f"ошибка отправки формы: {exc}")
        return
    text = " ".join(re.sub(r"<[^>]+>", " ", res.text).split())
    log(f"ответ формы: {res.status_code} url={res.url}")
    log("текст: " + text[:400])
    (OUT / "registration-result.html").write_text(res.text, encoding="utf-8")
    (OUT / "registration-session.json").write_text(
        json.dumps({c.name: c.value for c in session.cookies}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ROOT / "credentials-firewhite.json").write_text(
        json.dumps({"nick": NICK, "password": PASSWORD}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    bad = any(word in text.lower() for word in ("ошиб", "уже занят", "неверн", "невозможн"))
    RESULT["ok"] = not bad
    RESULT["text"] = text[:300]


def worker(raw: str) -> None:
    if DONE.is_set():
        return
    proxy = f"http://{raw}"
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    session.proxies.update({"http": proxy, "https": proxy})
    try:
        resp = session.get("https://barbars.ru/start", timeout=12)
    except Exception:  # noqa: BLE001
        session.close()
        return
    body = resp.text
    if "Долина варваров" in body or "registrationForm" in body:
        log(f"ВОРОНКА ОТКРЫТА через {raw}")
        try:
            register(session, body)
        finally:
            session.close()
        DONE.set()
        return
    session.close()


def main() -> int:
    log(f"ник={NICK} пароль={PASSWORD}")
    proxies: list[str] = []
    for src in SOURCES:
        try:
            text = requests.get(src, timeout=20).text
        except Exception:  # noqa: BLE001
            continue
        proxies.extend(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", text))
    proxies = list(dict.fromkeys(proxies))
    log(f"прокси: {len(proxies)}")
    with ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(worker, p) for p in proxies[:1500]]
        for future in as_completed(futures):
            if DONE.is_set():
                break
            future.result()
    if RESULT.get("ok"):
        log("АККАУНТ СОЗДАН")
        return 0
    log("регистрация не удалась")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
