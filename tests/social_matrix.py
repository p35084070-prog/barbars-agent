"""Матрица социальных входов: с посадочной страницей и channelId."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

PATHS = [
    "spaceslogin",
    "odnoklassnikilogin",
    "mailrulogin",
    "mailcataloglogin",
    "moimirlogin",
]
PREFIXES = [
    [],
    ["https://barbars.ru/?channelId=35"],
    ["https://barbars.ru/start"],
    ["https://barbars.ru/guild/16675"],
]

for path in PATHS:
    for prefix in PREFIXES:
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
        for step in prefix:
            session.get(step, timeout=25)
        try:
            resp = session.get(f"https://barbars.ru/{path}", timeout=25, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001
            print(f"{path:22} prefix={prefix[-1][-24:] if prefix else '-':24} ОШИБКА {exc}")
            continue
        chain = " -> ".join(r.headers.get("location", "")[:70] for r in resp.history)
        print(
            f"{path:22} prefix={(prefix[-1].split('/')[-1] if prefix else '-'):16} "
            f"{resp.status_code} final={resp.url[:70]} len={len(resp.text)}"
        )
        if resp.history:
            print(f"     цепочка: {chain}")
