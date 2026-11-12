"""Вкладка «Вещи» в форме отправки: как выбрать и отправить вещь."""
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
    if not m2:
        print("вкладки «Вещи» нет")
        return 1
    url2 = urljoin(f"{BASE}/user/mail/send/id/{FIREWHITE}", m2.group(1).replace("&amp;", "&"))
    h2 = s.get(url2, timeout=30, headers={"Referer": f"{BASE}/user/mail/send/id/{FIREWHITE}"})
    t2 = " ".join(text_of(h2.text).split())
    print("ВКЛАДКА «ВЕЩИ»:", t2[:900])
    print("\n  wicket-ссылки:", [l for l in dict.fromkeys(re.findall(r'href="([^"]*wicket[^"]*)"', h2.text))][:16])
    print("  input:", re.findall(r"<input[^>]*name=[\"']([^\"']+)[\"'][^>]*>", h2.text)[:12])
    print("  item/id:", list(dict.fromkeys(re.findall(r"item/id/(\d+)", h2.text)))[:12])
    print("  кнопки:", re.findall(r">([^<>]{2,30})</(?:a|button|input)>", h2.text)[:18])
    return 0


if __name__ == "__main__":
    sys.exit(main())
