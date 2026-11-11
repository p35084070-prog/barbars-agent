"""Параллельный поиск прокси, с которого barbars.ru открывает воронку регистрации."""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://api.codetabs.com/v1/proxy?quest=random",
]

STOP = threading.Event()
FOUND: list[str] = []


def log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", flush=True)


def collect() -> list[str]:
    proxies: list[str] = []
    for src in SOURCES:
        try:
            text = requests.get(src, timeout=20).text
        except Exception:  # noqa: BLE001
            continue
        proxies.extend(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", text))
    unique = list(dict.fromkeys(proxies))
    log(f"прокси в списках: {len(unique)}")
    return unique


def check(raw: str) -> tuple[str, str, int, bool] | None:
    proxy = f"http://{raw}"
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    session.proxies.update({"http": proxy, "https": proxy})
    try:
        ip = session.get("https://api.ipify.org", timeout=8).text.strip()
        resp = session.get("https://barbars.ru/start", timeout=10)
    except Exception:  # noqa: BLE001
        session.close()
        return None
    body = resp.text
    valley = "Долина варваров" in body or "registrationForm" in body
    session.close()
    return raw, ip, len(body), valley


def main() -> None:
    proxies = collect()
    tested = 0
    with ThreadPoolExecutor(max_workers=40) as pool:
        futures = {pool.submit(check, p): p for p in proxies[:800]}
        for future in as_completed(futures):
            tested += 1
            result = future.result()
            if result is None:
                continue
            raw, ip, length, valley = result
            log(f"{raw} exit={ip} len={length} {'<<< ВОРОНКА' if valley else ''}")
            if valley:
                FOUND.append(raw)
                Path("proxy_hit.txt").write_text(raw, encoding="utf-8")
                STOP.set()
                break
            if tested % 25 == 0:
                log(f"проверено {tested}")
    if FOUND:
        log(f"НАЙДЕН ПРОКСИ: {FOUND[0]}")
    else:
        log("подходящий прокси не найден")


if __name__ == "__main__":
    main()
