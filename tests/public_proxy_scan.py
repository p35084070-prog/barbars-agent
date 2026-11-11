"""Ищет рабочий публичный HTTPS-прокси, с которого открывается воронка регистрации.

Запросы идут через CONNECT-прокси с проверкой TLS-сертификата, поэтому
содержимое (в том числе пароль нового героя) прокси-сервер не видит.
"""
from __future__ import annotations

import random
import re
import time
from datetime import datetime

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def collect() -> list[str]:
    proxies: list[str] = []
    for src in SOURCES:
        try:
            text = requests.get(src, timeout=25).text
        except Exception as exc:  # noqa: BLE001
            log(f"источник недоступен {src}: {exc}")
            continue
        found = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", text)
        proxies.extend(found)
        log(f"{src.split('/')[-1]}: {len(found)} прокси")
    unique = list(dict.fromkeys(proxies))
    random.shuffle(unique)
    return unique


def main() -> None:
    proxies = collect()
    log(f"всего уникальных: {len(proxies)}")
    tried = 0
    for raw in proxies:
        if tried >= 60:
            break
        tried += 1
        proxy = f"http://{raw}"
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
        session.proxies.update({"http": proxy, "https": proxy})
        try:
            ip = session.get("https://api.ipify.org", timeout=12).text.strip()
            resp = session.get("https://barbars.ru/start", timeout=15)
        except Exception as exc:  # noqa: BLE001
            session.close()
            continue
        body = resp.text
        valley = "Долина варваров" in body
        form = "registrationForm" in body
        log(f"{raw} IP={ip} len={len(body)} долина={valley} форма={form}")
        if valley or form:
            log(f"ПОДХОДЯЩИЙ ПРОКСИ: {raw}")
            with open("proxy_hit.txt", "w", encoding="utf-8") as fh:
                fh.write(raw)
            session.close()
            return
        session.close()
    log("подходящий прокси не найден")


if __name__ == "__main__":
    main()
