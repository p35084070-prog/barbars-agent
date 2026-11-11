"""Проверяет, есть ли рабочий исходящий прокси (сменить IP) для регистрации."""
from __future__ import annotations

import requests

CANDIDATES = [
    "http://127.0.0.1:10809",
    "http://127.0.0.1:7890",
    "http://127.0.0.1:1080",
    "socks5://127.0.0.1:10808",
    "socks5h://127.0.0.1:10808",
]

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def direct_ip() -> str:
    try:
        return requests.get("https://api.ipify.org", timeout=15).text.strip()
    except Exception as exc:  # noqa: BLE001
        return f"ошибка: {exc}"


print("прямой IP:", direct_ip())

for proxy in CANDIDATES:
    proxies = {"http": proxy, "https": proxy}
    try:
        ip = requests.get("https://api.ipify.org", proxies=proxies, timeout=15).text.strip()
    except Exception as exc:  # noqa: BLE001
        print(f"{proxy:32} не работает ({type(exc).__name__})")
        continue
    print(f"{proxy:32} IP={ip}")
    try:
        resp = requests.get(
            "https://barbars.ru/start",
            proxies=proxies,
            headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"},
            timeout=25,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"{proxy:32} barbars недоступен: {type(exc).__name__}")
        continue
    body = resp.text
    print(
        f"{proxy:32} barbars: {resp.status_code} len={len(body)} "
        f"долина={'Долина варваров' in body} форма={'registrationForm' in body} url={resp.url}"
    )
