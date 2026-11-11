"""Ловит «редкий» ответ /start (третий бэкенд) и сохраняет его целиком."""
from __future__ import annotations

import re
import time
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)
OUT = Path(__file__).resolve().parents[1] / "knowledge" / "discovered"
OUT.mkdir(parents=True, exist_ok=True)

seen: set[int] = set()
for attempt in range(1, 400):
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    try:
        resp = session.get("https://barbars.ru/start", timeout=25)
    except Exception as exc:  # noqa: BLE001
        print(f"[{attempt}] ошибка {exc}", flush=True)
        continue
    body = resp.text
    if len(body) in (1928, 2060):
        seen.add(len(body))
        print(f"[{attempt}] len={len(body)} (известный)", flush=True)
    else:
        print(f"[{attempt}] НОВЫЙ ответ len={len(body)} url={resp.url}", flush=True)
        (OUT / f"start-{len(body)}.html").write_text(body, encoding="utf-8")
        text = re.sub(r"<script.*?</script>", " ", body, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        print("   текст:", " ".join(text.split())[:600], flush=True)
        for tag in re.findall(r"<(?:input|select)[^>]*>", body, re.IGNORECASE):
            print("    поле:", " ".join(tag.split()), flush=True)
        for href, t in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body, re.IGNORECASE | re.DOTALL):
            print("    ссылка:", href, "|", " ".join(re.sub(r"<[^>]+>", " ", t).split())[:50], flush=True)
        break
    time.sleep(0.4)
print("видимое разнообразие:", sorted(seen), flush=True)
