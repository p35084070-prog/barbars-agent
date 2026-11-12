r"""Экспорт сессии ОК из профиля Chromium — только cookie, компактно.

Зачем: профиль целиком занимает десятки мегабайт и не влезает в GitHub Secrets
(лимит ~48 КБ). Но сессия ОК — это по сути несколько cookie. Проверяем, хватает
ли их, чтобы открыть игру в свежем браузере без профиля.

Запуск:
    python tools\ok_export_cookies.py                 # в JSON-файл
    python tools\ok_export_cookies.py --base64        # в base64 (для секрета)
    python tools\ok_export_cookies.py --print-only    # показать в консоль
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile-ok-phone"
OUT = ROOT / "state" / "ok-session.json"

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)

# Куки, которые реально нужны для сессии ОК.
ESSENTIAL = {"domain_sid", "sid", "JSESSIONID", "ENVOY_JSESSIONID", "remixerp",
              "user_id", "lp", "__last_online", "fpId", "tkn", "bci"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="profile-ok-phone")
    ap.add_argument("--base64", action="store_true", help="вывести в base64")
    ap.add_argument("--print-only", action="store_true", help="только в консоль")
    ap.add_argument("--all", action="store_true", help="выгрузить все cookie ОК")
    args = ap.parse_args()

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / args.profile),
            headless=True,
            viewport={"width": 390, "height": 844},
            user_agent=IPHONE_UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://m.ok.ru/", wait_until="domcontentloaded", timeout=45_000)
        page.wait_for_timeout(3000)

        cookies = ctx.cookies()
        session = {c["name"]: c for c in cookies
                   if (args.all and "ok.ru" in c["domain"]) or c["name"] in ESSENTIAL}

        has = {c["name"] for c in cookies}
        print(f"всего cookie: {len(cookies)} | выгружаем: {len(session)}")
        print(f"domain_sid: {'есть' if 'domain_sid' in has else 'НЕТ'} | "
              f"sid: {'есть' if 'sid' in has else 'нет'}")
        ctx.close()

    payload = {"ua": IPHONE_UA, "cookies": list(session.values()),
               "at": datetime.now().isoformat(timespec="seconds")}

    if args.print_only:
        if args.base64:
            print(base64.b64encode(gzip.compress(
                json.dumps(payload).encode())).decode())
        else:
            print(json.dumps(payload, ensure_ascii=False))
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=1).encode()
    OUT.write_bytes(raw)
    packed = base64.b64encode(gzip.compress(raw)).decode()
    (OUT.parent / "ok-session.b64").write_text(packed, encoding="utf-8")
    print(f"записано: {OUT} ({len(raw)} байт), base64+gz: {len(packed)} байт")
    print(f"имена: {sorted(session)}")


if __name__ == "__main__":
    main()
