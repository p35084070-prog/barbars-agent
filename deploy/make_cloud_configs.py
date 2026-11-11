"""Собрать облачные конфиги из локальных (Linux-пути, headless, свои каталоги).

    python deploy/make_cloud_configs.py

Для GitHub Actions:
  * credentials_file — относительный путь, файл создаётся на раннере из секретов;
  * daily_file — отдельный файл дневных счётчиков, он коммитится в репозиторий
    (диск между запусками стирается, без этого лимиты сбрасывались бы ежедневно).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy"

CRED_DIR = "/opt/barbars-agent/credentials"


def patch(
    src: str,
    dst: str,
    profile: str,
    state: str,
    account: str,
    cred: str,
    daily: str,
) -> None:
    cfg = json.loads((ROOT / src).read_text(encoding="utf-8"))
    cfg["profile_dir"] = profile
    cfg["headless"] = True
    cfg["state_dir"] = state
    cfg["daily_file"] = daily
    cfg["account"] = account
    cfg.setdefault("auth", {})["credentials_file"] = cred
    cfg["auth"].pop("username_env", None)
    cfg["auth"].pop("password_env", None)
    (OUT / dst).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("записан:", dst)


def patch_actions(src: str, dst: str, profile: str, account: str, daily: str) -> None:
    """Конфиг для GitHub Actions: относительные пути внутри репозитория."""
    cfg = json.loads((ROOT / src).read_text(encoding="utf-8"))
    cfg["profile_dir"] = profile
    cfg["headless"] = True
    cfg["state_dir"] = f"logs/{account}"
    cfg["daily_file"] = daily
    cfg["account"] = account
    cfg.setdefault("auth", {})["credentials_file"] = f"credentials/{account}.txt"
    cfg["auth"].pop("username_env", None)
    cfg["auth"].pop("password_env", None)
    (OUT / dst).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("записан:", dst)


patch("config.json", "config-cloud-keis.json", "profile-keis", "logs/keis", "keis", "keis.txt", "state/keis/daily.json")
patch(
    "config-firewhite.json",
    "config-cloud-firewhite.json",
    "profile-firewhite",
    "logs/firewhite",
    "firewhite",
    "firewhite.txt",
    "state/firewhite/daily.json",
)
patch_actions("config.json", "config-actions-keis.json", "profile-keis", "keis", "state/keis/daily.json")
patch_actions(
    "config-firewhite.json",
    "config-actions-firewhite.json",
    "profile-firewhite",
    "firewhite",
    "state/firewhite/daily.json",
)
