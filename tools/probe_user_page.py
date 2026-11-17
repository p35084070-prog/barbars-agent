"""Разведка страницы героя: как пишется усталость (для сторожа башен).

Печатает строки страницы, где есть «устал/вынос/башн», и первые строки текста.
Только чтение.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars.driver import Game, _norm_text  # noqa: E402
from run import load_config  # noqa: E402

KEY = re.compile(r"устал|вынос|башн|труд|отдых|%|железо|мифрил", re.IGNORECASE)


def click_by_text(game: object, wanted: str) -> bool:
    """Кликнуть по элементу с текстом с учётом омоглифов игры.

    Игра маскирует часть букв латинскими («Войти» → «Boйти»), поэтому
    обычный `:has-text()` по сырому тексту такие кнопки не находит.
    """
    want = _norm_text(wanted)
    for tag in ("a", "button", "input", "span", "div"):
        try:
            elements = game.p.locator(tag).all()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            continue
        for element in elements:
            try:
                raw = element.inner_text() or ""
                if not raw and tag == "input":
                    raw = element.get_attribute("value") or ""
            except Exception:  # noqa: BLE001
                continue
            if _norm_text(raw).startswith(want):
                try:
                    element.scroll_into_view_if_needed(timeout=3000)
                    element.click(timeout=8000)
                    game._settle()  # type: ignore[attr-defined]
                    return True
                except Exception:  # noqa: BLE001
                    continue
    return False


def tower_scan(game: object, max_map: int = 4, max_near: int = 3) -> list[dict]:
    """Перебрать локации башни и найти страницу с ВИДИМОЙ кнопкой удара.

    Повторяет логику агента (open_tower): карта башен → ссылка локации →
    соседние стороны. Для каждой страницы записываем видимые боевые ссылки.
    """
    result: list[dict] = []

    def visible_fights() -> list[dict]:
        found: list[dict] = []
        try:
            links = game.p.locator("a").all()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return found
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                text = " ".join((link.inner_text() or "").split())[:50]
                if "damage" not in href and "attack" not in href:
                    continue
                if not link.is_visible():
                    found.append({"text": text, "href": href[:70], "visible": False})
                    continue
                found.append({"text": text, "href": href[:70], "visible": True})
            except Exception:  # noqa: BLE001
                continue
        return found

    def click(element: object) -> bool:
        try:
            element.scroll_into_view_if_needed(timeout=3000)  # type: ignore[attr-defined]
            element.click(timeout=8000)  # type: ignore[attr-defined]
            game._settle()  # type: ignore[attr-defined]
            return True
        except Exception:  # noqa: BLE001
            return False

    for map_index in range(max_map):
        game.goto("https://barbars.ru/game/towers")  # type: ignore[attr-defined]
        try:
            links = game.p.locator("a[href*='locationLink']").all()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            break
        if not links:
            break
        target = links[min(map_index, len(links) - 1)]
        try:
            name = " ".join((target.inner_text() or "").split())[:40]
        except Exception:  # noqa: BLE001
            name = ""
        if not click(target):
            continue
        result.append({"where": f"map[{map_index}] {name}", "fights": visible_fights()})
        for near_index in range(max_near):
            game.goto("https://barbars.ru/game/towers")  # type: ignore[attr-defined]
            try:
                links = game.p.locator("a[href*='locationLink']").all()  # type: ignore[attr-defined]
                near = game.p.locator("a[href*='locationLink']").all()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                break
            if not links:
                break
            if not click(links[min(map_index, len(links) - 1)]):
                break
            if not near:
                break
            near_target = near[min(near_index, len(near) - 1)]
            try:
                near_name = " ".join((near_target.inner_text() or "").split())[:40]
            except Exception:  # noqa: BLE001
                near_name = ""
            if not click(near_target):
                continue
            result.append({
                "where": f"map[{map_index}] -> near[{near_index}] {near_name}",
                "fights": visible_fights(),
            })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--url", default="/user")
    parser.add_argument("--click-location", action="store_true",
                        help="перейти в локацию башни и снять страницу боя")
    parser.add_argument("--click-text", action="append", default=[],
                        help="кликнуть по ссылке с этим текстом (можно несколько раз)")
    parser.add_argument("--wait-after", type=int, default=0,
                        help="сколько секунд ждать после последнего клика")
    parser.add_argument("--tower-scan", action="store_true",
                        help="перебрать локации башни и найти страницу с видимым ударом")
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    label = args.label or str(config.get("account") or args.config)
    out: dict[str, object] = {"label": label, "url": args.url}

    with tempfile.TemporaryDirectory(prefix=f"probe-{label}-") as tmp:
        game = None
        if config.get("ok_channel"):
            from barbars.ok_channel import OkGame

            game = OkGame(config, Path(tmp))
        else:
            game = Game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=120):
                out["error"] = "вход не подтверждён"
                print("PROBE_USER " + json.dumps(out, ensure_ascii=False), flush=True)
                return 1
            game.goto("https://barbars.ru" + args.url)
            if args.tower_scan:
                out["tower_scan"] = tower_scan(game)
            if args.click_location:
                loc = game.p.locator("a[href*='locationLink']")
                if loc.count():
                    try:
                        loc.first.click(timeout=8000)
                        game._settle()
                        out["clicked_location"] = " ".join((loc.first.inner_text() or "").split())
                    except Exception as exc:  # noqa: BLE001
                        out["click_error"] = str(exc).splitlines()[0][:200]
                else:
                    out["click_error"] = "нет ссылок локаций"
            text = game.body_text()
            for wanted in args.click_text:
                if click_by_text(game, wanted):
                    out.setdefault("clicked_text", []).append(wanted)
                else:
                    out.setdefault("click_errors", []).append(f"{wanted}: не найдено")
            if args.wait_after:
                time.sleep(args.wait_after)
                text = game.body_text()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            out["lines_matched"] = [l for l in lines if KEY.search(l)][:40]
            out["head"] = lines[:12]
            if "bg" in args.url:
                from barbars import pages

                out["battlefields"] = pages.parse_battlefields(game.p.content(), text)
            links = []
            for link in game.p.locator("a").all():
                try:
                    links.append({
                        "text": " ".join((link.inner_text() or "").split())[:60],
                        "href": (link.get_attribute("href") or "")[:90],
                    })
                except Exception:  # noqa: BLE001
                    continue
            out["all_links"] = links
            out["inputs"] = [
                {"name": el.get_attribute("name"), "type": el.get_attribute("type"),
                 "value": (el.get_attribute("value") or "")[:40]}
                for el in game.p.locator("input").all()
            ]
            out["buttons"] = [
                {"text": " ".join((b.inner_text() or "").split())[:50],
                 "name": b.get_attribute("name"), "value": (b.get_attribute("value") or "")[:30]}
                for b in game.p.locator("button").all()
            ]
            try:
                out["fatigue_api"] = game.hero_fatigue()
            except Exception as exc:  # noqa: BLE001
                out["fatigue_error"] = str(exc).splitlines()[0][:200]
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("PROBE_USER " + json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
