"""Ищет канал (channelId), который открывает регистрацию на barbars.ru."""
from __future__ import annotations

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

hits = []
for channel in range(0, 60):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    for path in (f"/?channelId={channel}", f"/registration?channelId={channel}", f"/start?channelId={channel}"):
        try:
            resp = session.get("https://barbars.ru" + path, timeout=15)
        except Exception:  # noqa: BLE001
            continue
        body = resp.text
        if "registrationForm" in body or "Игровое имя" in body or "Долина варваров" in body:
            hits.append((channel, path, len(body), resp.url))
            print("ПОПАДАНИЕ:", channel, path, len(body), resp.url, flush=True)
print("итого попаданий:", len(hits))
