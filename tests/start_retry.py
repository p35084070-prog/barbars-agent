"""Проверяет, как часто /start отдаёт «Долину варваров» (вход в регистрацию)."""
from __future__ import annotations

import time

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

for attempt in range(1, 9):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    resp = session.get("https://barbars.ru/start", timeout=25)
    valley = "Долина варваров" in resp.text
    fight = "Сразиться" in resp.text
    print(f"попытка {attempt}: status={resp.status_code} len={len(resp.text)} url={resp.url} долина={valley} сразиться={fight}")
    if valley:
        reg = session.get("https://barbars.ru/registration", timeout=25)
        print(f"   /registration -> len={len(reg.text)} форма={'registrationForm' in reg.text}")
    time.sleep(1.5)
