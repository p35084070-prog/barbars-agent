"""Ищет рабочий выход прокси, с которого открывается воронка регистрации.

Прокси-мост может выдавать разные IP; нужно найти тот, с которого barbars.ru
отдаёт «Долину варваров», и на нём же пройти регистрацию.
"""
from __future__ import annotations

import random
import time
from datetime import datetime

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
PROXY = "http://127.0.0.1:10809"
PROXIES = {"http": PROXY, "https": PROXY}


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def main() -> None:
    seen: dict[str, int] = {}
    for attempt in range(1, 61):
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9", "Connection": "close"})
        session.proxies.update(PROXIES)
        try:
            ip = session.get("https://api.ipify.org", timeout=15).text.strip()
        except Exception as exc:  # noqa: BLE001
            ip = f"ошибка {type(exc).__name__}"
        try:
            resp = session.get("https://barbars.ru/start", timeout=25)
            length = len(resp.text)
            valley = "Долина варваров" in resp.text
            form = "registrationForm" in resp.text
        except Exception as exc:  # noqa: BLE001
            length, valley, form = 0, False, False
            log(f"[{attempt}] IP={ip} ошибка {type(exc).__name__}")
        seen[ip] = seen.get(ip, 0) + 1
        log(f"[{attempt}] IP={ip} len={length} долина={valley} форма={form}")
        if valley or form:
            log("ВОРОНКА ОТКРЫТА — IP найден")
            session.close()
            return
        session.close()
        time.sleep(0.5 + random.random())
    log("подходящий IP не найден; встреченные:", seen)


if __name__ == "__main__":
    main()
