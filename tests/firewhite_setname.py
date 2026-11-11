"""Ставит ник «Fire White» новому герою (страница «Сохранить героя»)."""
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
WANTED = sys.argv[1] if len(sys.argv) > 1 else "Fire White"


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
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="barbars.ru", path="/")

    resp = session.get("https://barbars.ru/registration", timeout=30)
    print("страница:", resp.status_code, resp.url)
    body = text_of(resp.text)
    print("текст:", body[:350])
    action = re.search(r'<form[^>]*action="([^"]+)"[^>]*method="post"', resp.text)
    if not action:
        print("формы нет")
        return 1
    fields = form_inputs(resp.text)
    print("поля:", list(fields))
    for tag in re.findall(r"<(?:select)[^>]*>", resp.text, re.I):
        print("   ", " ".join(tag.split()))
    target = urljoin(resp.url, action.group(1))
    data = dict(fields)
    data["login"] = WANTED
    data["sex"] = "m"
    data["side"] = "1"
    data["type"] = "1"
    res = session.post(target, data=data, timeout=30, headers={"Referer": resp.url})
    print("ответ:", res.status_code, res.url)
    print("текст:", text_of(res.text)[:350])
    (ROOT / "knowledge" / "discovered" / "firewhite-setname.html").write_text(res.text, encoding="utf-8")
    page = session.get("https://barbars.ru/user", timeout=30)
    print("герой:", text_of(page.text)[:220])
    return 0


if __name__ == "__main__":
    sys.exit(main())
