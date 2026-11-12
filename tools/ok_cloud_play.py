r"""Запуск игры «Варвары» через ОК в облаке (GitHub Actions).

Схема:
  1. На ПК выполняется разовый вход (tools\ok_phone.py) и экспорт сессии
     (tools\ok_export_cookies.py). Сессия — это 6 cookie общим размером
     ~700 байт в base64, она помещается в GitHub Secret.
  2. На раннере CI мы поднимаем Chromium с мобильной эмуляцией ОК,
     восстанавливаем cookie, делаем handshake (m.ok.ru/app/barbars) —
     игра открывается в iframe od.barbars.ru.
  3. Дальше работаем ВНУТРИ кадра: у игры своя java-сессия в ;jsessionid=,
     обычная навигация по URL без него уводит на /authorization.

Ключевые особенности канала ОК (в отличие от прямого barbars.ru):
  * игра — в iframe, а не на верхнем уровне страницы;
  * ссылки относительные и содержат ;jsessionid=;
  * переходы делаются через клик по ссылке либо через goto с jsessionid.

Запуск локально:
    python tools\ok_cloud_play.py --session state/ok-session.b64
В CI:
    python tools\ok_cloud_play.py --session "$OK_SESSION_B64" --hold 3600
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)

MOBILE_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
    "Sec-CH-UA-Platform-Version": '"13.0.0"',
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
}

APP_URL = "https://m.ok.ru/app/barbars"
GAME_HOST = "https://od.barbars.ru"

# Маркеры игрового меню — по ним кадр игры опознаётся, когда его URL пуст.
GAME_MARKERS = ("Сражения", "Торговля", "Мой герой", "Мой клан", "Купить золото")


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_session(raw: str) -> tuple[list[dict], str]:
    """Принимает base64(gzip(json)) или готовый JSON."""
    raw = raw.strip()
    if raw.startswith("{"):
        payload = json.loads(raw)
    else:
        payload = json.loads(gzip.decompress(base64.b64decode(raw)))
    return payload.get("cookies", []), payload.get("ua", IPHONE_UA)


def wait_game_frame(page, tries: int = 30, wait: int = 5):
    """Ждём кадр с игрой.

    ОК периодически пересоздаёт игровой iframe, и тогда его URL становится
    пустым — искать только по URL нельзя. Поэтому сначала пробуем URL,
    а если не нашли — содержимое кадра (маркеры игрового меню).
    """
    for i in range(tries):
        time.sleep(wait)
        # 1) по URL
        for f in page.frames:
            if f == page.main_frame:
                continue
            if "od.barbars.ru" in f.url:
                try:
                    if f.inner_text("body", timeout=4000).strip():
                        return f
                except Exception:  # noqa: BLE001
                    continue
        # 2) по содержимому
        for f in page.frames:
            if f == page.main_frame:
                continue
            try:
                txt = f.inner_text("body", timeout=4000)
            except Exception:  # noqa: BLE001
                continue
            if sum(1 for m in GAME_MARKERS if m in txt) >= 3:
                return f
        if i % 3 == 0:
            log(f"   ждём кадр игры ({i + 1}/{tries})...")
    return None


def jsessionid_of(frame) -> str:
    """Ищем java-сессию игры: сначала в HTML кадра, потом в его URL."""
    try:
        html = frame.content()
    except Exception:  # noqa: BLE001
        html = ""
    m = re.search(r"jsessionid=([A-Za-z0-9]+)", html)
    if m:
        return m.group(1)
    m = re.search(r"jsessionid=([A-Za-z0-9]+)", frame.url)
    return m.group(1) if m else ""


class OkGameSession:
    """Сессия игры через ОК: отдаёт кадр, готовый к работе."""

    def __init__(self, page, frame):
        self.page = page
        self.frame = frame
        self.jsessionid = jsessionid_of(frame)

    def url_for(self, path: str) -> str:
        """Абсолютный URL игровой страницы с сохранением сессии."""
        if path.startswith("http"):
            url = path
        else:
            url = GAME_HOST + ("/" + path.lstrip("/"))
        if self.jsessionid and "jsessionid=" not in url:
            url = f"{url};jsessionid={self.jsessionid}"
        return url

    def goto(self, path: str, timeout: int = 45_000) -> bool:
        url = self.url_for(path)
        try:
            self.frame.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            log(f"переход не удался ({path}): {exc}")
            return False
        time.sleep(1.5)
        if "authorization" in self.frame.url:
            log(f"сессия потеряна на {path} — нужен новый handshake")
            return False
        return True

    def click_text(self, text: str, timeout: int = 15_000) -> bool:
        try:
            link = self.frame.query_selector(f"a:has-text('{text}')")
        except Exception:  # noqa: BLE001
            link = None
        if not link:
            return False
        try:
            link.click(timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            log(f"клик «{text}» не удался: {exc}")
            return False
        time.sleep(2)
        return True

    def text(self) -> str:
        try:
            return " ".join(self.frame.inner_text("body").split())
        except Exception:  # noqa: BLE001
            return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Игра через ОК в облаке")
    ap.add_argument("--session", default="", help="base64(gzip(json)) или путь к файлу")
    ap.add_argument("--session-file", default="state/ok-session.b64")
    ap.add_argument("--profile", default="profile-ok-cloud")
    ap.add_argument("--hold", type=int, default=0, help="сколько секунд играть")
    ap.add_argument("--out", default="logs/ok-cloud")
    ap.add_argument("--headless", action="store_true", default=True)
    ap.add_argument("--headed", dest="headless", action="store_false")
    args = ap.parse_args()

    raw = args.session
    if not raw:
        path = ROOT / args.session_file
        if not path.exists():
            log(f"НЕТ ФАЙЛА СЕССИИ: {path}")
            log("Создайте его на ПК: python tools\\ok_export_cookies.py")
            return 2
        raw = path.read_text(encoding="utf-8")

    cookies, ua = load_session(raw)
    log(f"сессия: {len(cookies)} cookie")

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / args.profile),
            headless=args.headless,
            viewport={"width": 390, "height": 844},
            user_agent=ua,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers=MOBILE_HEADERS,
            args=["--disable-blink-features=AutomationControlled", "--touch-events=enabled"],
        )
        ctx.add_cookies(cookies)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        log(f"handshake: {APP_URL}")
        try:
            page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            log(f"ошибка перехода: {exc}")

        frame = wait_game_frame(page)
        if frame is None:
            log("❌ ИГРА НЕ ЗАГРУЗИЛАСЬ")
            try:
                page.screenshot(path=str(out_dir / f"no-game-{stamp}.png"))
            except Exception:  # noqa: BLE001
                pass
            ctx.close()
            return 1

        session = OkGameSession(page, frame)
        log(f"✅ игра открыта, jsessionid={session.jsessionid[:12]}…")
        log(f"   герой: {session.text()[:160]}")

        try:
            page.screenshot(path=str(out_dir / f"game-{stamp}.png"))
        except Exception:  # noqa: BLE001
            pass

        # Проверка переходов по игровым страницам.
        for path in ("/game/towers", "/user/rack", "/trade/well"):
            ok = session.goto(path)
            log(f"   {path}: {'✅' if ok else '❌'} {session.text()[:110]}")

        # Возврат на главную игры.
        session.goto("/")

        if args.hold:
            log(f"играю {args.hold} сек")
            deadline = time.time() + args.hold
            while time.time() < deadline:
                time.sleep(10)
                if "od.barbars.ru" not in session.frame.url:
                    log("кадр игры потерян — переподключаю")
                    page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
                    frame = wait_game_frame(page)
                    if frame is None:
                        break
                    session = OkGameSession(page, frame)
                    continue
                log(f"   {session.text()[:120]}")

        (out_dir / f"session-{stamp}.json").write_text(
            json.dumps({"jsessionid": session.jsessionid, "frame": session.frame.url[:300],
                        "text": session.text()[:500]}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        ctx.close()
    log("готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
