"""Витрина игрока с id и форма отправки почты (с выбором вещей)."""
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

    h = s.get(f"{BASE}/user/public/store/id/{KEIS}", timeout=30)
    t = " ".join(text_of(h.text).split())
    print(f"=== витрина keis ({h.url}, len {len(h.text)})")
    print("  ", t[:700])
    print("  toRack:", list(dict.fromkeys(re.findall(r'href="([^"]*toRackLink[^"]*)"', h.text)))[:8])
    print("  items:", list(dict.fromkeys(re.findall(r"item/id/(\d+)", h.text)))[:8])

    h2 = s.get(f"{BASE}/user/mail/send/id/{KEIS}", timeout=30)
    t2 = " ".join(text_of(h2.text).split())
    print(f"\n=== форма отправки ({h2.url}, len {len(h2.text)})")
    print("  ", t2[:800])
    print("  input:", re.findall(r"<input[^>]*name=[\"']([^\"']+)[\"'][^>]*>", h2.text)[:12])
    print("  textarea:", re.findall(r"<textarea[^>]*name=[\"']([^\"']+)[\"']", h2.text)[:3])
    print("  select:", re.findall(r"<select[^>]*name=[\"']([^\"']+)[\"']", h2.text)[:5])
    print("  wicket-ссылки:", [l for l in dict.fromkeys(re.findall(r'href="([^"]*wicket[^"]*)"', h2.text))][:14])
    print("  кнопки:", re.findall(r">([^<>]{2,30})</(?:a|button|input)>", h2.text)[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main())
