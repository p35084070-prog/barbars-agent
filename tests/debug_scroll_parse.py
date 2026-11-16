"""v12: отладка разбора свитков на сохранённом HTML сундука."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from barbars.driver import NAME_BLOCK_RE  # noqa: E402

RAW = Path(__file__).resolve().parent / "raw"
html = (RAW / "keis_chest.html").read_text(encoding="utf-8")

print("NAME_BLOCK_RE всего:", len(NAME_BLOCK_RE.findall(html)))
print("первые:", NAME_BLOCK_RE.findall(html)[:5])
found = []
for chunk in html.split('<div class="hr"></div>'):
    if "Свиток" not in chunk and "Манускрипт" not in chunk:
        continue
    m = NAME_BLOCK_RE.search(chunk)
    found.append((m.group(1) if m else None, m.group(2) if m else None))
print("по блокам:", found[:6])
# вариант без деления на блоки
ids = []
for m in NAME_BLOCK_RE.finditer(html):
    chunk = html[max(0, m.start() - 600):m.end() + 200]
    if "Свиток" in chunk or "Манускрипт" in chunk:
        ids.append((m.group(1), m.group(2)))
print("окном ±600:", ids[:8])
