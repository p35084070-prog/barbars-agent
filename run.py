"""CLI агента «Варвары».

  python run.py login      # открыть браузер и залогиниться вручную (пароль нам не нужен)
  python run.py play       # автономная игра
  python run.py play-ok    # автономная игра через мобильную версию ОК
  python run.py once       # один цикл решений
  python run.py discover   # выгрузить страницы игры для разбора
  python run.py doctor     # проверить окружение
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from barbars import pages
from barbars.driver import Game, GameError
from barbars.loop import Agent

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.json"


def load_config(path: str | Path) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise SystemExit(f"Нет файла конфигурации: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    # Cloud configs live under deploy/, but credentials/state/logs are rooted
    # at the repository. Keep legacy config-relative paths unless opted in.
    base = Path(__file__).resolve().parent if config.get("paths_relative_to") == "repository" else config_path.resolve().parent
    config["_root"] = str(base)
    return config


def profile_dir(config: dict) -> Path:
    raw = config.get("profile_dir", "profile")
    path = Path(raw)
    if not path.is_absolute():
        path = Path(config["_root"]) / path
    return path


def state_dir(config: dict) -> Path:
    """Каталог логов и дневных счётчиков — свой для каждого аккаунта."""
    raw = config.get("state_dir") or "logs"
    path = Path(raw)
    if not path.is_absolute():
        path = Path(config["_root"]) / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def cmd_login(config: dict) -> int:
    print("Открываю браузер. Войди в игру вручную (логин/пароль), затем вернись сюда.")
    game = Game(config, profile_dir(config))
    game.start(headless=False)
    try:
        game.goto("https://barbars.ru/")
        print("Ожидаю авторизацию...")
        if not game.wait_for_login(timeout_sec=600):
            print("Не дождался авторизации — закрой окно и запусти снова.")
            return 1
        print("Готово: сессия авторизована.")
        game.dump_page("after-login", profile_dir(config) / "snapshots")
        if config.get("run", {}).get("login_then_play"):
            print("Продолжаю автономную игру в этом же окне. Ctrl+C — остановить.")
            agent = Agent(game, config, log_dir=state_dir(config))
            agent.run_forever()
        return 0
    finally:
        game.close()


def cmd_play(config: dict, headless: bool | None, iterations: int, duration_min: float = 0.0) -> int:
    game = Game(config, profile_dir(config))
    game.start(headless=headless)
    if not game.ensure_login(timeout_sec=int(config.get("run", {}).get("login_timeout_sec", 600))):
        print("Не удалось авторизоваться — перезапусти и войди вручную.")
        game.close()
        return 1
    agent = Agent(game, config, log_dir=state_dir(config))
    try:
        agent.run_forever(max_iterations=iterations, duration_sec=duration_min * 60)
    except KeyboardInterrupt:
        agent.log("остановлено пользователем")
    finally:
        agent.dump_state()
        game.close()
    return 0


def cmd_play_ok(config: dict, headless: bool | None, iterations: int,
                duration_min: float = 0.0) -> int:
    """Игра через мобильную версию Одноклассников.

    Сессия ОК берётся из переменной OK_SESSION_B64 (или файла
    ok_channel.session_file из конфига) — это несколько cookie, которые
    на ПК готовит tools\\ok_export_cookies.py.
    """
    from barbars.ok_channel import OkGame

    game = OkGame(config, profile_dir(config))
    try:
        game.start(headless=headless)
    except GameError as exc:
        print(f"[ОК] не удалось открыть игру: {exc}")
        return 1
    if not game.ensure_login(timeout_sec=int(config.get("run", {}).get("login_timeout_sec", 600))):
        print("Не удалось войти в игру через ОК.")
        game.close()
        return 1
    expected = config.get("expected_hero")
    if expected:
        try:
            hero = verify_expected_hero(game, expected)
            config["_verified_hero_maxima"] = {k: getattr(hero, k, None) for k in ("max_hp", "max_energy")
                                               if isinstance(getattr(hero, k, None), (int, float)) and getattr(hero, k) > 0}
        except GameError as exc:
            print(str(exc))
            game.close()
            return 1
    agent = Agent(game, config, log_dir=state_dir(config))
    try:
        agent.run_forever(max_iterations=iterations, duration_sec=duration_min * 60)
    except KeyboardInterrupt:
        agent.log("остановлено пользователем")
    finally:
        agent.dump_state()
        game.close()
    return 0


def verify_expected_hero(game, expected: dict):
    """Reject a wrong OK session before the new account can do anything."""
    game.goto("https://barbars.ru/user")
    hero = game.hero()
    if (str(game.hero_id) != str(expected.get("id"))
            or hero.klass != expected.get("class")
            or str(hero.guild_id) != str(expected.get("guild_id"))):
        raise GameError("ОК: ID, класс или клан не совпадают с настроенным героем; действия запрещены")
    print(f"[ОК] герой подтверждён: id={game.hero_id}, класс={hero.klass}, клан={hero.guild_id}", flush=True)
    return hero


def cmd_once(config: dict, headless: bool | None) -> int:
    game = Game(config, profile_dir(config))
    game.start(headless=headless)
    if not game.ensure_login(timeout_sec=int(config.get("run", {}).get("login_timeout_sec", 600))):
        print("Не удалось авторизоваться.")
        game.close()
        return 1
    agent = Agent(game, config, log_dir=state_dir(config))
    try:
        decision = agent.run_once()
        print("итоговое решение:", decision)
    finally:
        game.close()
    return 0


def cmd_discover(config: dict) -> int:
    """Сохранить HTML+текст ключевых страниц — чтобы допилить селекторы."""
    out = Path(config["_root"]) / "knowledge" / "discovered"
    out.mkdir(parents=True, exist_ok=True)
    game = Game(config, profile_dir(config))
    game.start(headless=False)
    pages_to_dump = [
        ("home", "https://barbars.ru/"),
        ("hero", "https://barbars.ru/user"),
        ("fightmore", "https://barbars.ru/fightmore"),
        ("dungeons", "https://barbars.ru/game/dungeons"),
        ("towers", "https://barbars.ru/game/towers"),
        ("stances", "https://barbars.ru/user/stances"),
        ("abilities", "https://barbars.ru/user/abilities/0"),
        ("profession", "https://barbars.ru/user/profession"),
        ("resources", "https://barbars.ru/user/resources"),
        ("journey", "https://barbars.ru/journey"),
        ("quests", "https://barbars.ru/user/quests"),
        ("well", "https://barbars.ru/trade/well"),
        ("shops", "https://barbars.ru/trade"),
    ]
    try:
        for name, url in pages_to_dump:
            try:
                game.goto(url)
                game.dump_page(name, out)
                print(f"сохранено: {name}")
            except Exception as exc:
                print(f"пропущено {name}: {exc}")
        if game.guild_id:
            game.goto(f"https://barbars.ru/guild/{game.guild_id}")
            game.dump_page("clan", out)
            game.goto(f"https://barbars.ru/guild/quests/0/{game.guild_id}")
            game.dump_page("clan-quests", out)
    finally:
        game.close()
    print(f"Файлы в {out}")
    return 0


def cmd_doctor(config: dict) -> int:
    ok = True
    try:
        import playwright  # noqa: F401

        print("[ok] playwright установлен")
    except Exception:
        ok = False
        print("[fail] нет playwright — выполни: pip install -r requirements.txt")
    profile = profile_dir(config)
    if profile.exists():
        print(f"[ok] профиль браузера: {profile}")
    else:
        print(f"[warn] профиль не создан — сначала: python run.py login")
    key = os.environ.get(config.get("llm", {}).get("api_key_env", "ANTHROPIC_API_KEY"), "")
    print(f"[{'ok' if key else 'warn'}] ANTHROPIC_API_KEY: {'задан' if key else 'не задан (работают только правила)'}")
    auth = config.get("auth", {})
    cred_file = Path(auth.get("credentials_file", "credentials.txt"))
    if not cred_file.is_absolute():
        cred_file = Path(config["_root"]) / cred_file
    if cred_file.exists():
        print(f"[ok] файл автовхода: {cred_file}")
    else:
        print(f"[warn] нет {cred_file.name} — при перезапуске браузера придётся войти вручную")
    if config.get("spend", {}).get("allow_gold_fights"):
        print("[warn] разрешены бои за золото")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Агент для игры «Варвары»")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("command",
                        choices=["login", "play", "play-ok", "once", "discover", "doctor"])
    parser.add_argument("--headless", action="store_true", help="без окна браузера")
    parser.add_argument("--iterations", type=int, default=0, help="сколько циклов (0 = бесконечно)")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="сколько минут работать, потом выйти (0 = бесконечно; для облака)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    headless = True if args.headless else None

    if args.command == "login":
        return cmd_login(config)
    if args.command == "play":
        return cmd_play(config, headless, args.iterations, args.duration)
    if args.command == "play-ok":
        return cmd_play_ok(config, headless, args.iterations, args.duration)
    if args.command == "once":
        return cmd_once(config, headless)
    if args.command == "discover":
        return cmd_discover(config)
    if args.command == "doctor":
        return cmd_doctor(config)
    return 1


if __name__ == "__main__":
    sys.exit(main())

