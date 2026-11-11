"""Форма выставления вещи на «Витрину клана»: панель toPublicStoreLink (без отправки)."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402

BASE = "https://barbars.ru"


def main() -> int:
    lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / "barbars-firewhite-credentials.txt").read_text(encoding="utf-8-sig").splitlines()]
    lines = [l for l in lines if l]
    s = login(lines[0], lines[1])
    rack = s.get(f"{BASE}/user/rack", timeout=30).text
    ids = re.findall(r'href="\.\./item/id/(\d+)"', rack)
    if not ids:
        print("нет вещей")
        return 1
    item_id = ids[0]
    page = s.get(f"{BASE}/item/id/{item_id}", timeout=30).text
    print("вещь:", " ".join(text_of(page).split())[:200])
    m = re.search(r'href="([^"]*toPublicStoreLink[^"]*)"', page)
    if not m:
        print("ссылки toPublicStoreLink нет")
        return 1
    url = urljoin(f"{BASE}/item/id/{item_id}", m.group(1).replace("&amp;", "&"))
    print("открываем:", url)
    res = s.get(url, timeout=30, headers={"Referer": f"{BASE}/item/id/{item_id}"})
    t = " ".join(text_of(res.text).split())
    print("ПАНЕЛЬ:", t[:900])
    print("поля ввода:", re.findall(r"<input[^>]*name=[\"']([^\"']+)[\"'][^>]*>", res.text)[:20])
    print("select:", re.findall(r"<select[^>]*name=[\"']([^\"']+)[\"']", res.text)[:10])
    for name in re.findall(r"<input[^>]*name=[\"']([^\"']+)[\"'][^>]*value=[\"']([^\"']*)[\"']", res.text)[:15]:
        print("   input:", name)
    print("кнопки:", re.findall(r">([^<>]{2,40})</(?:a|button|input)>", res.text)[:20])
    return 0


if __name__ == "__main__":
    sys.exit(main())
