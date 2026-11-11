"""Ставит пароль новому герою «Fire White» (шаг «Защита аккаунта»)."""
from __future__ import annotations

import json
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]
NICK = "Fire White"


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def form_inputs(html: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*>", html, re.I):
        name = re.search(r'name="([^"]+)"', tag)
        if not name:
            continue
        value = re.search(r'value="([^"]*)"', tag)
        data[name.group(1)] = value.group(1) if value else ""
    return data


def main() -> int:
    cookies = json.loads(
        (ROOT / "knowledge" / "discovered" / "registration-session.json").read_text(encoding="utf-8")
    )
    creds_path = ROOT / "credentials-firewhite.json"
    creds = json.loads(creds_path.read_text(encoding="utf-8")) if creds_path.exists() else {}
    password = creds.get("password") or ("Fw" + secrets.token_urlsafe(12))

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="barbars.ru", path="/")

    url = "https://barbars.ru/user/protection/0/1"
    resp = session.get(url, timeout=30)
    print("страница:", resp.status_code, resp.url)
    action = re.search(r'<form[^>]*action="([^"]+)"[^>]*method="post"', resp.text)
    if not action:
        print("форма пароля не найдена")
        print(text_of(resp.text)[:300])
        return 1
    target = urljoin(resp.url, action.group(1))
    data = form_inputs(resp.text)
    data["password"] = password
    data["password2"] = password
    print("action:", target, "поля:", list(data))

    res = session.post(target, data=data, timeout=30, headers={"Referer": resp.url})
    print("ответ:", res.status_code, res.url)
    print("текст:", text_of(res.text)[:400])
    (ROOT / "knowledge" / "discovered" / "firewhite-protection.html").write_text(res.text, encoding="utf-8")

    page = session.get("https://barbars.ru/user", timeout=30)
    body = text_of(page.text)
    print("страница героя:", page.status_code, body[:300])
    if "Выход" in body or NICK in body:
        creds_path.write_text(
            json.dumps({"nick": NICK, "password": password}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("ПАРОЛЬ УСТАНОВЛЕН:", password)
        return 0
    print("похоже, пароль не применился")
    return 2


if __name__ == "__main__":
    sys.exit(main())
