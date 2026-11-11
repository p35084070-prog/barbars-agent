"""Регистрация «Fire White» через найденный прокси (чистый IP → воронка открыта)."""
from __future__ import annotations

import json
import random
import re
import secrets
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

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


def try_proxy(raw: str) -> bool:
    proxy = f"http://{raw}"
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    session.proxies.update({"http": proxy, "https": proxy})
    try:
        resp = session.get("https://barbars.ru/start", timeout=30)
    except Exception as exc:  # noqa: BLE001
        log(f"{raw}: ошибка {exc}")
        session.close()
        return False

    html = resp.text
    log(f"{raw}: len={len(html)} долина={'Долина варваров' in html}")
    if "Долина варваров" not in html and "registrationForm" not in html:
        session.close()
        return False

    if "registrationForm" not in html:
        fight = re.search(r'href="([^"]*attackLink[^"]*)"', html)
        if not fight:
            session.close()
            return False
        resp2 = session.get(urljoin(resp.url, fight.group(1)), timeout=30, headers={"Referer": resp.url})
        html = resp2.text

    parsed = find_form(html)
    if not parsed:
        (OUT / "registration-attempt.html").write_text(html, encoding="utf-8")
        log("форма не распознана, сохранил дамп")
        session.close()
        return False

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
        elif low in ("captcha", "code", "verify"):
            log("нужен captcha — вручную")
            session.close()
            return False

    target = "https://barbars.ru/" + action.lstrip("/")
    res = session.post(target, data=data, timeout=30, headers={"Referer": "https://barbars.ru/registration"})
    text = " ".join(re.sub(r"<[^>]+>", " ", res.text).split())
    log(f"ответ: {res.status_code} url={res.url}")
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
    bad = any(word in text.lower() for word in ("ошиб", "уже занят", "неверн", "невозможн"))
    return not bad


def main() -> int:
    log(f"ник={NICK} пароль={PASSWORD}")
    hit = ROOT / "proxy_hit.txt"
    if not hit.exists():
        log("нет proxy_hit.txt")
        return 1
    raw = hit.read_text(encoding="utf-8").strip()
    if try_proxy(raw):
        log("АККАУНТ СОЗДАН")
        return 0
    log("не удалось зарегистрироваться")
    return 1


if __name__ == "__main__":
    sys.exit(main())
