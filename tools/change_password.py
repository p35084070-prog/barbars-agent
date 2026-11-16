"""Сменить пароль героя на странице «Защита аккаунта».

Нужен, когда пароль попал в git-историю: сначала меняем пароль в игре,
потом чистим репозиторий.

Запуск: python tools\\change_password.py <ник> <старый_пароль> <новый_пароль>
"""
from __future__ import annotations

import re
import sys

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.I | re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.split())


def login(nick: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    page = s.get("https://barbars.ru/login", timeout=25)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', page.text)
    res = s.post(
        "https://barbars.ru/" + form.group(1).lstrip("/"),
        data={"login": nick, "password": password},
        timeout=25,
        headers={"Referer": page.url},
    )
    print("вход:", res.status_code, res.url)
    return s


def main() -> int:
    nick, old_pw, new_pw = sys.argv[1], sys.argv[2], sys.argv[3]
    account = ""
    if len(sys.argv) > 4 and sys.argv[4] == "--update-secret":
        account = sys.argv[5] if len(sys.argv) > 5 else ""
    s = login(nick, old_pw)
    changed = False
    for url in ("https://barbars.ru/user/protection/0/1", "https://barbars.ru/user/protection"):
        res = s.get(url, timeout=25)
        print(f"\n=== {url} :: {res.status_code} {res.url}")
        print("текст:", text_of(res.text)[:700])
        action = re.search(r'<form[^>]*action="([^"]+)"[^>]*method="post"', res.text)
        if not action:
            continue
        hidden = {
            n: v
            for n, v in re.findall(
                r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', res.text
            )
        }
        fields = re.findall(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', res.text)
        print("форма:", action.group(1), "поля:", fields)
        data = dict(hidden)
        for name in fields:
            low = name.lower()
            if "pass2" in low or low.endswith("2"):
                data[name] = new_pw
            elif "pass" in low:
                # поле старого пароля (oldPassword / currentPassword) — старое,
                # остальные — новый
                if "old" in low or "current" in low or "wrong" in low:
                    data[name] = old_pw
                else:
                    data[name] = new_pw
        target = "https://barbars.ru/" + action.group(1).lstrip("/")
        out = s.post(target, data=data, timeout=25, headers={"Referer": res.url})
        print("ответ:", out.status_code, out.url)
        print("текст:", text_of(out.text)[:700])
        low = text_of(out.text).lower()
        if "установлен" in low or "измен" in low or "пароль" in low and "готов" in low:
            changed = True
            break
    # проверка: вход с новым паролем
    s2 = login(nick, new_pw)
    home = s2.get("https://barbars.ru/user", timeout=25)
    body = text_of(home.text)
    entered = "Вход" not in body[:200] and "Регистрация" not in body[:200]
    print("\nвход с новым паролем:", "успешно" if entered else body[:200])
    ok = changed and entered
    if ok and account:
        import subprocess

        subprocess.run(
            ["gh", "secret", "set", f"BARBARS_{account.upper()}_PASSWORD",
             "-R", "p35084070-prog/barbars-agent"],
            input=new_pw,
            text=True,
            check=True,
        )
        print(f"секрет BARBARS_{account.upper()}_PASSWORD обновлён")
    print("PASSWORD_CHANGED" if ok else "PASSWORD_NOT_CHANGED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
