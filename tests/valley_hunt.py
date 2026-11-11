"""Охотится за страницей «Долина варваров» и доходит до формы регистрации.

Сервер редко отдаёт эту страницу, поэтому перебираем попытки; как только
долина найдена — идём по её ссылке «Сразиться!» и смотрим форму регистрации.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

ATTEMPTS = 30


def dump_fields(html: str) -> None:
    print("   поля формы:")
    for tag in re.findall(r"<(?:input|select)[^>]*>", html, re.IGNORECASE):
        print("     ", " ".join(tag.split()))
    for block in re.findall(r"<select[^>]*>.*?</select>", html, re.IGNORECASE | re.DOTALL):
        for opt in re.findall(r"<option[^>]*>", block, re.IGNORECASE):
            print("      option:", " ".join(opt.split()))
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    print("   текст:", " ".join(text.split())[:800])


for attempt in range(1, ATTEMPTS + 1):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    resp = session.get("https://barbars.ru/start", timeout=25)
    if "Долина варваров" not in resp.text:
        print(f"попытка {attempt}: тир ({len(resp.text)} байт)")
        time.sleep(0.7)
        continue

    print(f"попытка {attempt}: ДОЛИНА найдена!")
    href = re.search(r'href="([^"]*attackLink[^"]*)"', resp.text)
    print("   ссылка боя:", href.group(1) if href else None)
    if href:
        fight_url = urljoin(resp.url, href.group(1))
        fight = session.get(fight_url, timeout=25, headers={"Referer": resp.url})
        print("   после боя:", fight.status_code, len(fight.text), fight.url)
        if "registrationForm" in fight.text:
            print("   ФОРМА РЕГИСТРАЦИИ НАЙДЕНА")
            dump_fields(fight.text)
            break
        else:
            print("   текст:", " ".join(re.sub(r"<[^>]+>", " ", fight.text).split())[:400])
            reg = session.get("https://barbars.ru/registration", timeout=25)
            print("   /registration:", reg.status_code, len(reg.text))
            if "registrationForm" in reg.text:
                print("   ФОРМА РЕГИСТРАЦИИ НАЙДЕНА")
                dump_fields(reg.text)
                break
    time.sleep(0.7)
