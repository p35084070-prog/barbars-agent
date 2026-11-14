"""Разведка зала кланового босса: кто в зале, кто готов, что с драконом.

Только чтение: агент не вступает в бой, не жмёт «Я готов!» и не меняет
готовность. Нужен, чтобы проверить, собираются ли все четверо наших героев
(keis, firewhite, vagojan через ОК, qdal через ОК2) в одном зале.

    python tools/probe_raid_room.py --config config-ok2.json --label ok2
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars.driver import Game  # noqa: E402
from run import load_config, profile_dir, verify_expected_hero  # noqa: E402


def build_game(config: dict, profile: Path):
    """ОК-канал или обычный вход — по наличию секции ok_channel в конфиге."""
    if config.get("ok_channel"):
        from barbars.ok_channel import OkGame

        return OkGame(config, profile)
    return Game(config, profile)


def main() -> int:
    parser = argparse.ArgumentParser(description="Пробник зала босса")
    parser.add_argument("--config", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--url", default="https://barbars.ru/game/dragonDungeon")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="logs")
    args = parser.parse_args()

    config = load_config(ROOT / args.config)
    label = args.label or str(config.get("account") or args.config)
    out: dict[str, object] = {"label": label, "config": args.config}
    result = 0

    with tempfile.TemporaryDirectory(prefix=f"probe-{label}-") as tmp:
        game = build_game(config, Path(tmp))
        try:
            game.start(headless=True)
            if not game.ensure_login(timeout_sec=args.timeout):
                out["error"] = "вход не подтверждён"
                result = 1
                print("PROBE_ROOM " + json.dumps(out, ensure_ascii=False), flush=True)
                return _finish(out, args.out, label, result)
            out["hero_id"] = str(getattr(game, "hero_id", "") or "")
            expected = config.get("expected_hero")
            if expected:
                try:
                    verify_expected_hero(game, expected)
                    out["expected_hero"] = "подтверждён"
                except Exception as exc:  # noqa: BLE001
                    out["expected_hero"] = "НЕ СОВПАЛ: " + str(exc).splitlines()[0][:200]
                    print("PROBE_ROOM " + json.dumps(out, ensure_ascii=False), flush=True)
                    return _finish(out, args.out, label, 1)
            try:
                hero = game.hero()
                out["hero_class"] = getattr(hero, "klass", "")
                out["guild_id"] = str(getattr(hero, "guild_id", "") or "")
                out["level"] = getattr(hero, "level", None)
            except Exception as exc:  # noqa: BLE001
                out["hero_error"] = str(exc).splitlines()[0][:200]
            try:
                out["clan_kills"] = game.raid_clan_kills()
            except Exception as exc:  # noqa: BLE001
                out["clan_kills_error"] = str(exc).splitlines()[0][:200]
            room = game.raid_room(args.url)
            out["room"] = {
                "closed": room.get("closed"),
                "reopen_in": room.get("reopen_in"),
                "hp": room.get("hp"),
                "warriors": room.get("warriors"),
                "healers": room.get("healers"),
                "limit": room.get("limit"),
                "can_start": room.get("can_start"),
                "in_fight": room.get("in_fight"),
                "locked_out": room.get("locked_out"),
                "ready": room.get("ready"),
                "waiting": room.get("waiting"),
            }
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc).splitlines()[0][:300]
        finally:
            try:
                game.close()
            except Exception:  # noqa: BLE001
                pass

    print("PROBE_ROOM " + json.dumps(out, ensure_ascii=False), flush=True)
    return _finish(out, args.out, label, result)


def _finish(out: dict, out_dir: str, label: str, code: int) -> int:
    """Сохранить снимок зала в logs/ и напечатать строку PROBE_ROOM."""
    try:
        directory = Path(out_dir)
        if not directory.is_absolute():
            directory = ROOT / directory
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"probe-room-{label}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print("не удалось сохранить снимок:", exc)
    return code


if __name__ == "__main__":
    sys.exit(main())
