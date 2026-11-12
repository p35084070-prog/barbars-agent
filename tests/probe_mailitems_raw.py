"""Как выбираются вещи во вкладке «Вещи» формы отправки (сырой HTML)."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
FIREWHITE = "31389504"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-agentcredentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    h = s.get(f"{BASE}/user/mail/send/id/{FIREWHITE}", timeout=30)
    m2 = re.search(r'href="([^"]*mailItemLink[^"]*)"', h.text)
    url2 = urljoin(f"{BASE}/user/mail/send/id/{FIREWHITE}", m2.group(1).replace("&amp;", "&"))
    h2 = s.get(url2, timeout=30, headers={"Referer": f"{BASE}/user/mail/send/id/{FIREWHITE}"})
    html = h2.text
    i = html.find("Выбраны вещи")
    if i < 0:
        i = html.find("Выбрать")
    print("HTML вокруг выбора вещей:\n")
    print(" ".join(html[max(0, i - 800):i + 3000].split())[:3500])
    print("\n\nвсе wicket-ссылки:", [l for l in dict.fromkeys(re.findall(r'href="([^"]*wicket[^"]*)"', html))][:24])
    print("checkbox/radio:", re.findall(r"<input[^>]*type=[\"']checkbox[\"'][^>]*>", html)[:10])
    print("item/id:", list(dict.fromkeys(re.findall(r"item/id/(\d+)", html)))[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
