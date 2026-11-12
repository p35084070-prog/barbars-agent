"""Отправка вещи/письма другому игроку: ссылка «Отправить почту» и форма."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"
KEIS = "905853"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    prof = s.get(f"{BASE}/user/id/{KEIS}", timeout=30).text
    t = " ".join(text_of(prof).split())
    i = t.find("Отправить почту")
    print("профиль:", t[max(0, i - 120):i + 160])
    links = [l for l in dict.fromkeys(re.findall(r'href="([^"]+)"', prof)) if not l.endswith(".css")]
    print("ссылки профиля:", links[:20])
    m = re.search(r'href="([^"]*)"[^>]*>\s*<span>\s*Отправить почту', prof)
    print("ссылка почты:", m.group(1) if m else "не найдена по тексту")
    if m:
        from urllib.parse import urljoin
        url = urljoin(f"{BASE}/user/id/{KEIS}", m.group(1).replace("&amp;", "&"))
        h = s.get(url, timeout=30, headers={"Referer": f"{BASE}/user/id/{KEIS}"})
        ht = " ".join(text_of(h.text).split())
        print("\nФОРМА ПОЧТЫ:", ht[:700])
        print("  поля:", re.findall(r"<input[^>]*name=[\"']([^\"']+)[\"']", h.text)[:10])
        print("  select:", re.findall(r"<select[^>]*name=[\"']([^\"']+)[\"']", h.text)[:5])
        print("  ссылки:", [l for l in dict.fromkeys(re.findall(r'href="([^"]*wicket[^"]*)"', h.text))][:12])
        print("  textarea:", re.findall(r"<textarea[^>]*name=[\"']([^\"']+)[\"']", h.text)[:3])
    return 0


if __name__ == "__main__":
    sys.exit(main())
