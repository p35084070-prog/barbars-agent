"""Разбор одной покупки в «Магазине снаряжения»: куда девается вещь.

Покупает самый дешёвый товар (не дороже 1 золота), печатает страницу сразу
после покупки (текст + все ссылки), кошелёк, надетое снаряжение, рюкзак,
витрину и сундук.

Запуск: python tools\\probe_buy_once.py <ник> <пароль> [id_героя]
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars import pages  # noqa: E402
from barbars.driver import Game  # noqa: E402
from run import load_config  # noqa: E402


def dump_links(game: Game, limit: int = 60) -> None:
    html = game.p.content()
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        label = " ".join(re.sub("<[^>]+>", " ", m.group(2)).split())
        print(f"   {label[:45]:47} {m.group(1)[:110]}")
        limit -= 1
        if limit <= 0:
            return


def main() -> int:
    nick, password = sys.argv[1], sys.argv[2]
    hero_id = sys.argv[3] if len(sys.argv) > 3 else "905853"
    config = load_config(ROOT / "deploy/config-actions-keis.json")
    with tempfile.TemporaryDirectory(prefix="buy-once-") as tmp:
        game = Game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=120):
                print("вход не подтверждён")
                return 1
            game.goto(f"https://barbars.ru/user/body/id/{hero_id}")
            print("=== НАДЕТОЕ СНАРЯЖЕНИЕ ===")
            print(" ".join(game.body_text().split())[:1500])

            items = game.shop_gear("")
            priced = []
            for it in items:
                try:
                    g, s = game.shop_item_price(str(it.get("item_id")))
                except Exception:
                    continue
                priced.append((g * 100 + s, g, s, it))
            priced.sort(key=lambda x: x[0])
            if not priced:
                print("товары не найдены")
                return 1
            total, g, s, it = priced[0]
            print(f"\n=== ПОКУПАЮ: {it.get('name')} id {it.get('item_id')} цена {g} зол {s} сер")
            ok, msg = game.buy_shop_item_capped(str(it.get("item_id")), max_gold=1)
            print("результат:", ok, msg)
            print("URL после покупки:", game.p.url)
            print("текст страницы:", " ".join(game.body_text().split())[:900])
            print("--- ссылки страницы:")
            dump_links(game)
            st = game.status()
            print("кошелёк:", st.gold, "зол", st.silver, "сер")
            for path in ("/user/rack", "/user/public/store", "/user/store"):
                game.goto("https://barbars.ru" + path)
                names = []
                for chunk, index in game._item_blocks(game.p.content()):
                    m = re.search(r'item/id/\d+"><span>([^<]{2,60})</span>', chunk)
                    if m:
                        names.append(m.group(1).strip())
                print(f"{path}: {names}")
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
