"""Ловит редкий ответ /start (не 1928/2060) и показывает, что это."""
from __future__ import annotations

import re
import time

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

for attempt in range(1, 80):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    resp = session.get("https://barbars.ru/start", timeout=25)
    body = resp.text
    if len(body) not in (1928, 2060):
        print(f"попытка {attempt}: необычный ответ len={len(body)} url={resp.url}")
        text = re.sub(r"<script.*?</script>", " ", body, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        print("   текст:", " ".join(text.split())[:700])
        print("   форма:", "registrationForm" in body, "долина:", "Долина варваров" in body)
        for tag in re.findall(r"<(?:input|select)[^>]*>", body, re.IGNORECASE):
            print("    ", " ".join(tag.split()))
        for href, text2 in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.IGNORECASE | re.DOTALL):
            clean = " ".join(re.sub(r"<[^>]+>", " ", text2).split())
            print("    ссылка:", href, "|", clean[:50])
        break
    print(f"попытка {attempt}: len={len(body)}", flush=True)
    time.sleep(0.8)
