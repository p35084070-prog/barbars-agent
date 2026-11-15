"""Завершает регистрацию героя: ставит пароль на странице «Защита аккаунта».

После отправки формы регистрации игра открывает /user/protection/0/1 с формой
passwordForm (поля password и password2). Скрипт берёт cookies сессии
регистрации из JSON и досылает пароль.

Запуск: python tools\\finish_registration.py <session.json> <пароль>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
ROOT = Path(__file__).resolve().parents[1]


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def main() -> int:
    session_file = Path(sys.argv[1])
    password = sys.argv[2]
    cookies = json.loads(session_file.read_text(encoding="utf-8"))

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="barbars.ru", path="/")

    url = "https://barbars.ru/user/protection/0/1"
    resp = session.get(url, timeout=30)
    print("страница:", resp.status_code, resp.url, len(resp.text))
    print("текст:", text_of(resp.text)[:300])
    if "passwordForm" not in resp.text:
        print("формы пароля нет — сессия протухла")
        return 1
    action = re.search(r'<form[^>]*action="([^"]+)"', resp.text).group(1)
    hidden = {
        n: v
        for n, v in re.findall(
            r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', resp.text
        )
    }
    data = dict(hidden)
    data["password"] = password
    data["password2"] = password
    target = urljoin(resp.url, action)
    print("POST", target)
    res = session.post(target, data=data, timeout=30, headers={"Referer": resp.url})
    print("ответ:", res.status_code, res.url)
    print("текст:", text_of(res.text)[:400])
    page = session.get("https://barbars.ru/user", timeout=30)
    print("герой:", text_of(page.text)[:300])
    ids = sorted(set(re.findall(r"/user/id/(\d+)", page.text)))
    print("user-id:", ids)
    if "Выход" in text_of(page.text):
        print("сессия живая")
    out = ROOT / "knowledge" / "discovered" / "reg_artifact" / "steelblue-session.json"
    out.write_text(
        json.dumps({c.name: c.value for c in session.cookies}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("cookies сохранены:", out.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
