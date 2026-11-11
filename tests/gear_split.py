"""Кузнец (прокачка железом) + состав рюкзака/сундука обоих героев."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def smith(s):
    r = s.get("https://barbars.ru/trade/smith", timeout=30)
    html = r.text
    txt = " ".join(text_of(html).split())
    print("\n=== кузнец ===")
    print(" ", txt[:1400])
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, re.S | re.I):
        t = " ".join(text_of(m.group(2)).split())
        if re.search(r"(точ|улучш|закал|кузн|усил|желез)", t + m.group(1), re.I):
            print(f"   {t!r} -> {m.group(1).split('wicket:interface')[-1][:70]}")


def rack_items(s, label):
    for page, name in (("https://barbars.ru/user/rack", "рюкзак"), ("https://barbars.ru/user/store", "сундук")):
        html = s.get(page, timeout=30).text
        txt = " ".join(text_of(html).split())
        head = re.search(r"(Рюкзак|Сундук)\s*\((\d+)\s*/\s*(\d+)\)", txt)
        print(f"\n=== {label}: {name} {head.group(0) if head else '?'} ===")
        # блоки предметов
        blocks = html.split('<div class="hr"></div>')
        for chunk in blocks:
            t = " ".join(text_of(chunk).split())
            if not t or "Вернуться в бой" in t:
                continue
            if re.search(r"(wearLink|toStoreLink|crackLink|toRackLink|useLink|sendLink)", chunk):
                acts = []
                if "wearLink" in chunk:
                    acts.append("надеть")
                if "toStoreLink" in chunk:
                    acts.append("в сундук")
                if "crackLink" in chunk:
                    m = re.search(r"crackLink", chunk)
                    acts.append(f"разобрать({re.findall(r'crackIronPanel', chunk)})")
                if "toRackLink" in chunk:
                    acts.append("в рюкзак")
                if "useLink" in chunk:
                    acts.append("использовать")
                if "sendLink" in chunk:
                    acts.append("в хранилище")
                item = t.split("[")[0][:70]
                print(f"   {item!r} -> {acts}")


def main() -> int:
    for label, fname in (("keis", "barbars-agentcredentials.txt"),
                         ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / fname).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        if label == "keis":
            smith(s)
        rack_items(s, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
