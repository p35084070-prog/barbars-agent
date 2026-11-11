"""Проверяет соседние IP с тем же SOCKS-мостом: возможно, у провайдера есть пул выходов.

Учётные данные моста берём из C:\\ClaudeProxy\\bridge_config.json.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

cfg = json.loads(Path(r"C:\ClaudeProxy\bridge_config.json").read_text(encoding="utf-8"))
up = cfg["upstream_socks"]
base = up["host"].split(".")
prefix = ".".join(base[:3])

candidates = []
for last in range(max(1, int(base[3]) - 12), int(base[3]) + 13):
    candidates.append(f"{prefix}.{last}")

for host in candidates:
    proxy = f"socks5h://{up['user']}:{up['password']}@{host}:{up['port']}"
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    session.proxies.update({"http": proxy, "https": proxy})
    try:
        ip = session.get("https://api.ipify.org", timeout=12).text.strip()
        resp = session.get("https://barbars.ru/start", timeout=15)
    except Exception as exc:  # noqa: BLE001
        print(f"{host}: ошибка {type(exc).__name__}", flush=True)
        session.close()
        continue
    body = resp.text
    valley = "Долина варваров" in body
    print(
        f"{host}: exit={ip} len={len(body)} долина={valley} "
        f"форма={'registrationForm' in body}",
        flush=True,
    )
    if valley:
        Path("proxy_hit.txt").write_text(proxy, encoding="utf-8")
        print("ПОДХОДЯЩИЙ:", proxy, flush=True)
        session.close()
        break
    session.close()
