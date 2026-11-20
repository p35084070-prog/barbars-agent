r"""Ручной вход в ОК под второй аккаунт (Qdle/qdal) с автовыгрузкой сессии.

Зачем: tools\ok_phone.py ждёт нажатия Enter в консоли — в неинтерактивной
сессии (CI, фоновая задача) он сразу выходит. Этот скрипт ждёт появления
НАСТОЯЩЕЙ сессии (cookie remixerp/user_id/AUTHCODE, а не анонимные sid) и
сам сохраняет её в state\ok2-session.b64 в формате ok_export_cookies.py.

Запуск:
    python tools\ok2_wait_login.py                 # окно браузера, ждём входа
    python tools\ok2_wait_login.py --timeout 900

После успешного входа:
    gh secret set OK2_SESSION_B64 --repo p35084070-prog/barbars-agent `
        --body (Get-Content state\ok2-session.b64 -Raw).Trim()
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "profile-ok2-phone"
OUT_B64 = ROOT / "state" / "ok2-session.b64"
OUT_JSON = ROOT / "state" / "ok2-session.json"
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)
MOBILE_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
}
# Настоящая авторизация. Одной cookie sid/AUTHCODE не хватает: их ОК ставит и
# анонимным посетителям (тогда страница отдаёт «Вход в ОК»). Признак входа —
# cookie _userIds/_suserIds (или remixerp/user_id у новых версий).
AUTH_MARKERS = ("_userIds", "_suserIds", "remixerp", "user_id")
ESSENTIAL = {"domain_sid", "sid", "JSESSIONID", "ENVOY_JSESSIONID", "remixerp",
              "user_id", "lp", "__last_online", "fpId", "tkn", "bci"}


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def authorized(ctx) -> bool:
    try:
        names = {c["name"] for c in ctx.cookies()}
    except Exception:  # noqa: BLE001
        return False
    return bool(set(AUTH_MARKERS) & names)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--profile", default=PROFILE)
    args = ap.parse_args()

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / args.profile),
            headless=False,
            viewport={"width": 390, "height": 844},
            user_agent=IPHONE_UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
            extra_http_headers=MOBILE_HEADERS,
            args=["--disable-blink-features=AutomationControlled", "--touch-events=enabled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://m.ok.ru/", wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка перехода: {str(exc).splitlines()[0]}")
        log("окно ОК открыто — войдите под аккаунтом Qdle (qdal)")
        deadline = time.time() + args.timeout
        announced = False
        while time.time() < deadline:
            if authorized(ctx):
                log("✅ авторизация видна — сохраняю сессию")
                break
            if not announced:
                log("(ждём реального входа: cookie _userIds появляются только после входа)")
                announced = True
            time.sleep(2)
        else:
            log("❌ вход не завершён за отведённое время")
            ctx.close()
            return 4

        cookies = ctx.cookies()
        session = {c["name"]: c for c in cookies
                   if "ok.ru" in c["domain"] or c["name"] in ESSENTIAL}
        payload = {"ua": IPHONE_UA, "cookies": list(session.values()),
                   "at": datetime.now().isoformat(timespec="seconds")}
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, indent=1).encode()
        OUT_JSON.write_bytes(raw)
        packed = base64.b64encode(gzip.compress(raw)).decode()
        OUT_B64.write_text(packed, encoding="utf-8")
        log(f"сохранено: {OUT_B64} ({len(packed)} байт), cookie: {sorted(session)}")
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
