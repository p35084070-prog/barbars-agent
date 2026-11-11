"""Проверяет состояние нового героя: ник, id, вход по паролю."""
from __future__ import annotations

import json
import re
from pathlib import Path

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


def main() -> None:
    cookies = json.loads(
        (ROOT / "knowledge" / "discovered" / "registration-session.json").read_text(encoding="utf-8")
    )
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="barbars.ru", path="/")

    resp = session.get("https://barbars.ru/user", timeout=30)
    print("url:", resp.url, resp.status_code)
    print("текст:", text_of(resp.text)[:400])
    print("id героя:", sorted(set(re.findall(r"user/id/(\d+)", resp.text))))
    for link, text in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.I | re.S):
        clean = " ".join(re.sub(r"<[^>]+>", " ", text).split())
        if clean:
            print(f"   {link} | {clean[:40]}")
    print("cookies сейчас:", {c.name: c.value[:40] for c in session.cookies})
    (ROOT / "knowledge" / "discovered" / "firewhite-session.json").write_text(
        json.dumps({c.name: c.value for c in session.cookies}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    creds = json.loads((ROOT / "credentials-firewhite.json").read_text(encoding="utf-8"))
    print("пробуем вход как", creds["nick"])
    s2 = requests.Session()
    s2.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    login_page = s2.get("https://barbars.ru/login", timeout=30)
    form = re.search(r'<form action="([^"]+)"[^>]*method="post"', login_page.text)
    res = s2.post("https://barbars.ru/" + form.group(1).lstrip("/"),
                  data={"login": creds["nick"], "password": creds["password"]},
                  timeout=30, headers={"Referer": login_page.url})
    print("вход:", text_of(res.text)[:250])
    if "Выход" in res.text:
        print("ВХОД РАБОТАЕТ")
        (ROOT / "knowledge" / "discovered" / "firewhite-login.json").write_text(
            json.dumps({c.name: c.value for c in s2.cookies}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
