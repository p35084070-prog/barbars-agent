"""Сырое состояние ресурсов и героя (для проверки, идёт ли фарм в облаке)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_state import DESKTOP, login, text_of  # noqa: E402


def main() -> int:
    for label, filename in (("keis", "barbars-agentcredentials.txt"),
                            ("firewhite", "barbars-firewhite-credentials.txt")):
        lines = [l.strip().lstrip("\ufeff") for l in (DESKTOP / filename).read_text(encoding="utf-8-sig").splitlines()]
        lines = [l for l in lines if l]
        s = login(lines[0], lines[1])
        res = text_of(s.get("https://barbars.ru/user/resources", timeout=30).text)
        hero = text_of(s.get("https://barbars.ru/user", timeout=30).text)
        flat_res = " ".join(res.split())
        flat_hero = " ".join(hero.split())
        iron = re.search(r"Железо:\s*([\d\s,]+)", flat_res)
        mif = re.search(r"Мифрил:\s*([\d\s,]+)", flat_res)
        bot = re.search(r"Бутылочки:\s*([\d\s,]+)", flat_res)
        exp = re.search(r"опыт:\s*([\d.,]+[kKmMgG]?)\s*/\s*([\d.,]+[kKmMgG]?)", flat_hero)
        lvl = re.search(r"(\d+)\s*ур,\s*(воин|медик)", flat_hero)
        part = re.search(r"участие:\s*([\d.,]+[kKmMgG]?)", flat_hero)
        print(
            f"{label}: ур={lvl.group(1) if lvl else '?'} "
            f"опыт={exp.group(1) + '/' + exp.group(2) if exp else '?'} "
            f"участие={part.group(1) if part else '?'} "
            f"железо={iron.group(1).strip() if iron else '?'} "
            f"мифрил={mif.group(1).strip() if mif else '?'} "
            f"бутылки={bot.group(1).strip() if bot else '?'}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
