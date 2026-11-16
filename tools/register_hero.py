"""Регистрация нового героя на barbars.ru: терпеливый опрос воронки.

Сервер открывает форму регистрации не всем сессиям сразу: новому игроку
показывается «Долина варваров», а форма — только из воронки (после боя).
Скрипт крутит свежие сессии (прямой IP и через локальный прокси) и, как только
форма появилась, сразу её заполняет и отправляет.

Поля формы: ник (2–16 символов, ≤2 пробелов), пол (m/f), сторона
(1 = север, 2 = юг), класс (1 = воин, 2 = медик).

Запуск: python tools\\register_hero.py <ник> [класс] [сторона] [пароль] [попыток] [аккаунт]
Аккаунт (логическое имя) по умолчанию берётся из HERO_ACCOUNT, иначе "steelblue";
от него зависят имена файлов credentials-<аккаунт>.json и registration-<аккаунт>*.json.
"""
from __future__ import annotations

import json
import os
import random
import re
import secrets
import sys
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
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

NICK = sys.argv[1] if len(sys.argv) > 1 else "Steel Blue ii"
KIND = sys.argv[2] if len(sys.argv) > 2 else "1"
SIDE = sys.argv[3] if len(sys.argv) > 3 else "1"
PASSWORD = sys.argv[4] if len(sys.argv) > 4 else ""
if not PASSWORD:
    # требование игры: не менее 6 символов, буквы + цифры
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    PASSWORD = "Sb" + "".join(secrets.choice(alphabet) for _ in range(12))
MAX_TRIES = int(sys.argv[5]) if len(sys.argv) > 5 else 200
# логическое имя аккаунта: на него завязаны пути файлов и GitHub-секреты
ACCOUNT = sys.argv[6] if len(sys.argv) > 6 else os.environ.get("HERO_ACCOUNT", "steelblue")
MAIL = f"{ACCOUNT}{random.randint(1000, 9999)}@mailinator.com"
CRED_FILE = ROOT / f"credentials-{ACCOUNT}.json"


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def new_session(use_proxy: bool) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    if use_proxy:
        s.proxies.update({"http": PROXY, "https": PROXY})
    return s


def find_form(html: str):
    if "registrationForm" not in html:
        return None
    action = re.search(r'<form[^>]*action="([^"]+)"', html)
    if not action:
        return None
    hidden = {
        n: v
        for n, v in re.findall(
            r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html
        )
    }
    fields = re.findall(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', html)
    return action.group(1), hidden, fields


def try_funnel(session: requests.Session):
    """/start → бой → страница с формой регистрации. Или /registration напрямую."""
    resp = session.get("https://barbars.ru/start", timeout=20)
    if "Долина варваров" in resp.text:
        fight = re.search(r'href="([^"]*attackLink[^"]*)"', resp.text)
        if fight:
            resp2 = session.get(
                urljoin(resp.url, fight.group(1)), timeout=20, headers={"Referer": resp.url}
            )
            parsed = find_form(resp2.text)
            if parsed:
                return resp2, parsed
    resp3 = session.get("https://barbars.ru/registration", timeout=20)
    parsed = find_form(resp3.text)
    if parsed:
        return resp3, parsed
    return None, None


def set_password(session: requests.Session, resp, password: str) -> tuple[str, str]:
    """Страница «Защита аккаунта»: после регистрации игра просит задать пароль.

    Возвращает (текст страницы, url).
    """
    if "Защита аккаунта" not in resp.text and "Установи пароль" not in resp.text:
        return "", ""
    log("страница защиты аккаунта — задаём пароль")
    action = re.search(r'<form[^>]*action="([^"]+)"[^>]*method="post"', resp.text)
    if not action:
        return text_of(resp.text)[:400], resp.url
    hidden = {
        n: v
        for n, v in re.findall(
            r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', resp.text
        )
    }
    fields = re.findall(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', resp.text)
    data = dict(hidden)
    for name in fields:
        low = name.lower()
        if "pass" in low:
            data[name] = password
    target = "https://barbars.ru/" + action.group(1).lstrip("/")
    res = session.post(target, data=data, timeout=25, headers={"Referer": resp.url})
    log(f"пароль отправлен: {res.status_code} len={len(res.text)} url={res.url}")
    log("текст: " + text_of(res.text)[:500])
    return text_of(res.text)[:800], res.url


def main() -> int:
    log(f"ник={NICK!r} класс={KIND} сторона={SIDE}")
    log(f"пароль={PASSWORD}")
    deadline = time.time() + 60 * 50
    attempt = 0
    while time.time() < deadline and attempt < MAX_TRIES:
        attempt += 1
        use_proxy = attempt % 2 == 0
        session = new_session(use_proxy)
        try:
            resp, parsed = try_funnel(session)
        except Exception as exc:  # noqa: BLE001
            log(f"[{attempt}] сетевая ошибка: {exc}")
            time.sleep(2)
            continue
        if not parsed:
            log(f"[{attempt}] формы нет ({'прокси' if use_proxy else 'прямой'})")
            time.sleep(1.5 + random.random() * 2.5)
            continue
        action, hidden, fields = parsed
        log(f"[{attempt}] ФОРМА! fields={fields}")
        data = dict(hidden)
        data.update({"login": NICK, "sex": "m", "side": SIDE, "type": KIND})
        for name in fields:
            low = name.lower()
            if low in ("login", "sex", "side", "type"):
                continue
            if "pass" in low:
                data[name] = PASSWORD
            elif "mail" in low:
                data[name] = MAIL
        target = "https://barbars.ru/" + action.lstrip("/")
        res = session.post(target, data=data, timeout=25, headers={"Referer": resp.url})
        log(f"ответ: {res.status_code} len={len(res.text)} url={res.url}")
        log("текст: " + text_of(res.text)[:600])
        set_password(session, res, PASSWORD)
        (OUT / f"registration-{ACCOUNT}.html").write_text(res.text, encoding="utf-8")
        (OUT / f"registration-{ACCOUNT}-session.json").write_text(
            json.dumps({c.name: c.value for c in session.cookies}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        CRED_FILE.write_text(
            json.dumps({"nick": NICK, "password": PASSWORD, "mail": MAIL}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log("сохранены cookies и учётные данные")
        return 0
    log("форма так и не появилась")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
