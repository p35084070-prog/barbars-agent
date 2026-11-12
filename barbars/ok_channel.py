r"""Адаптер канала ОК: даёт драйверу игру «Варвары» как обычную страницу.

Зачем
----
Драйвер агента (barbars/driver.py) работает со страницей barbars.ru: он ходит
по адресам вида /game/towers, /user/rack и разбирает HTML. По каналу ОК игра
живёт иначе:

  * открывается в iframe od.barbars.ru внутри страницы ОК;
  * сессия java-игры держится в ;jsessionid= прямо в URL;
  * ссылки в игре относительные и уже содержат ;jsessionid=.

Поэтому обычный переход по абсолютному URL без jsessionid уводит на
/authorization («только для зарегистрированных игроков»).

Этот модуль решает три задачи:
  1) OkFrameAdapter — обёртка над кадром игры с API, совместимым с Page
     (goto/locator/inner_text/content/...), причём goto сам дописывает
     jsessionid и ходит по относительным путям от текущего URL кадра;
  2) OkSession — установка handshake с ОК и поиск кадра игры;
  3) OkGame — готовая игра для агента: базовый URL переключается на
     od.barbars.ru, а логин не нужен (сессия уже есть).

Использование:
    from barbars.ok_channel import OkGame
    game = OkGame(config, profile_dir)
    game.start(headless=True)
    agent = Agent(game, config)
    agent.run_forever()
"""
from __future__ import annotations

import base64
import gzip
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import Frame, Page, sync_playwright

from .driver import Game, GameError

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

# Маркеры игрового меню: по ним кадр опознаётся, когда его URL пуст.
GAME_MARKERS = ("Сражения", "Торговля", "Мой герой", "Мой клан", "Купить золото")

JSESSION_RE = re.compile(r"jsessionid=([A-Za-z0-9]+)")


def load_session(raw: str) -> tuple[list[dict], str]:
    """Принимает base64(gzip(json)) либо готовый JSON с cookie."""
    raw = (raw or "").strip()
    if not raw:
        return [], IPHONE_UA
    if raw.startswith("{"):
        payload = json.loads(raw)
    else:
        payload = json.loads(gzip.decompress(base64.b64decode(raw)))
    return payload.get("cookies", []), payload.get("ua", IPHONE_UA)


def session_from_env(name: str = "OK_SESSION_B64") -> tuple[list[dict], str]:
    import os

    return load_session(os.environ.get(name, ""))


def session_from_file(path: str | Path) -> tuple[list[dict], str]:
    p = Path(path)
    if not p.exists():
        return [], IPHONE_UA
    return load_session(p.read_text(encoding="utf-8"))


class OkFrameAdapter:
    """Кадр игры как «страница»: методы те же, что у Page, но с учётом сессии."""

    def __init__(self, frame: Frame, page: Page):
        self._frame = frame
        self._page = page

    # -------------------------------------------------------------- состояние кадра
    @property
    def frame(self) -> Frame:
        return self._frame

    @property
    def page(self) -> Page:
        return self._page

    @property
    def url(self) -> str:
        return self._frame.url

    @property
    def title(self) -> str:
        try:
            return self._frame.title()
        except Exception:  # noqa: BLE001
            return ""

    def is_closed(self) -> bool:
        try:
            return self._frame.is_detached()
        except Exception:  # noqa: BLE001
            return True

    @property
    def jsessionid(self) -> str:
        """Java-сессия игры: ищем в HTML кадра, потом в его URL."""
        try:
            html = self._frame.content()
        except Exception:  # noqa: BLE001
            html = ""
        m = JSESSION_RE.search(html) or JSESSION_RE.search(self._frame.url)
        return m.group(1) if m else ""

    # -------------------------------------------------------------- навигация
    def _resolve(self, url: str) -> str:
        """Собрать абсолютный URL так, чтобы сохранить jsessionid."""
        if not url.startswith("http"):
            # относительный путь — от текущего URL кадра (там уже есть сессия)
            url = urljoin(self._frame.url, url)
        sid = self.jsessionid
        if sid and "jsessionid=" not in url and url.startswith(GAME_HOST):
            url = f"{url};jsessionid={sid}"
        return url

    def goto(self, url: str, wait_until: str = "domcontentloaded", **kwargs: Any) -> Any:
        target = self._resolve(url)
        return self._frame.goto(target, wait_until=wait_until, **kwargs)

    def reload(self, **kwargs: Any) -> Any:
        return self._frame.reload(**kwargs)

    def wait_for_load_state(self, state: str = "load", **kwargs: Any) -> Any:
        return self._frame.wait_for_load_state(state, **kwargs)

    # -------------------------------------------------------------- чтение
    def content(self) -> str:
        return self._frame.content()

    def inner_text(self, selector: str, **kwargs: Any) -> str:
        return self._frame.inner_text(selector, **kwargs)

    def text_content(self, selector: str, **kwargs: Any) -> str | None:
        return self._frame.text_content(selector, **kwargs)

    def locator(self, selector: str, **kwargs: Any) -> Any:
        return self._frame.locator(selector, **kwargs)

    def query_selector(self, selector: str, **kwargs: Any) -> Any:
        return self._frame.query_selector(selector, **kwargs)

    def query_selector_all(self, selector: str, **kwargs: Any) -> Any:
        return self._frame.query_selector_all(selector, **kwargs)

    def title_text(self) -> str:
        return self.title

    # -------------------------------------------------------------- ввод
    def fill(self, selector: str, value: str, **kwargs: Any) -> Any:
        return self._frame.locator(selector).fill(value, **kwargs)

    def click(self, selector: str, **kwargs: Any) -> Any:
        return self._frame.locator(selector).click(**kwargs)

    def select_option(self, selector: str, value: Any = None, **kwargs: Any) -> Any:
        return self._frame.locator(selector).select_option(value, **kwargs)

    def check(self, selector: str, **kwargs: Any) -> Any:
        return self._frame.locator(selector).check(**kwargs)

    def uncheck(self, selector: str, **kwargs: Any) -> Any:
        return self._frame.locator(selector).uncheck(**kwargs)

    def press(self, selector: str, key: str, **kwargs: Any) -> Any:
        return self._frame.locator(selector).press(key, **kwargs)

    # -------------------------------------------------------------- прочее
    def mouse(self) -> Any:
        """Мышь — у главной страницы (координаты кадра считаются от неё)."""
        return self._page.mouse

    def keyboard(self) -> Any:
        return self._page.keyboard

    def screenshot(self, **kwargs: Any) -> Any:
        return self._page.screenshot(**kwargs)

    def evaluate(self, expression: str, **kwargs: Any) -> Any:
        return self._frame.evaluate(expression, **kwargs)

    def frames(self) -> list[Frame]:
        return [self._frame]


class OkGame(Game):
    """Игра «Варвары», открытая через мобильную версию ОК.

    Отличие от обычной Game:
      * браузер поднимается в мобильной эмуляции (ОК иначе отдаёт десктоп);
      * сессия ОК восстанавливается из cookie (секрета CI);
      * вместо страницы игры драйвер получает кадр внутри iframe ОК;
      * логин по логину/паролю не нужен — сессия уже установлена.
    """

    def __init__(self, config: dict[str, Any], profile_dir: str | Path,
                 session_raw: str | None = None):
        super().__init__(config, profile_dir)
        self.session_raw = session_raw
        self.ok_page: Page | None = None
        self._adapter: OkFrameAdapter | None = None
        # Игра в канале ОК живёт на od.barbars.ru, а не на barbars.ru
        self.base_url = GAME_HOST + "/"

    # ------------------------------------------------------------------ сессия
    def _session(self) -> tuple[list[dict], str]:
        if self.session_raw:
            return load_session(self.session_raw)
        cfg = self.config.get("ok_channel", {})
        raw = cfg.get("session_file")
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                path = Path(self.config.get("_root", ".")) / path
            cookies, ua = session_from_file(path)
            if cookies:
                return cookies, ua
        cookies, ua = session_from_env(cfg.get("session_env", "OK_SESSION_B64"))
        return cookies, ua

    # ------------------------------------------------------------------ lifecycle
    def start(self, headless: bool | None = None) -> None:
        if self.page is not None:
            return
        headless = self.config.get("headless", False) if headless is None else headless
        self.headless = bool(headless)
        cookies, ua = self._session()
        if not cookies:
            print("[ОК] нет сессии ОК — задай OK_SESSION_B64 или ok_channel.session_file")
            raise GameError("Нет сессии ОК")

        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            self.profile_dir,
            headless=headless,
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
        self._context.set_default_timeout(20_000)
        self._context.add_cookies(cookies)
        self.ok_page = (self._context.pages[0] if self._context.pages
                        else self._context.new_page())

        frame = self._wait_game_frame()
        if frame is None:
            self.close()
            raise GameError("Игра через ОК не загрузилась")
        self._adapter = OkFrameAdapter(frame, self.ok_page)
        self.page = self._adapter  # type: ignore[assignment]

    def _wait_game_frame(self, tries: int = 30, wait: int = 5) -> Frame | None:
        """Handshake с ОК и поиск кадра с игрой (ОК троттлит частые входы)."""
        assert self.ok_page is not None
        print(f"[ОК] handshake: {APP_URL}")
        try:
            self.ok_page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:  # noqa: BLE001
            print(f"[ОК] ошибка перехода: {exc}")
        for i in range(tries):
            time.sleep(wait)
            for f in self.ok_page.frames:
                if f == self.ok_page.main_frame:
                    continue
                if "od.barbars.ru" in f.url:
                    try:
                        if f.inner_text("body", timeout=4000).strip():
                            return f
                    except Exception:  # noqa: BLE001
                        continue
            for f in self.ok_page.frames:
                if f == self.ok_page.main_frame:
                    continue
                try:
                    txt = f.inner_text("body", timeout=4000)
                except Exception:  # noqa: BLE001
                    continue
                if sum(1 for m in GAME_MARKERS if m in txt) >= 3:
                    return f
            if i % 3 == 0:
                print(f"[ОК] ждём кадр игры ({i + 1}/{tries})...")
        return None

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            if self._playwright:
                self._playwright.stop()
            self._context = None
            self._playwright = None
            self.page = None
            self.ok_page = None
            self._adapter = None

    # ------------------------------------------------------------------ логин
    def ensure_login(self, timeout_sec: int = 600) -> bool:
        """Сессия ОК уже даёт вход в игру — проверяем и всё."""
        if self.is_authenticated():
            return True
        # кадр мог не прогрузиться — пробуем дождаться
        if self.ok_page is not None:
            frame = self._wait_game_frame(tries=10)
            if frame is not None:
                self._adapter = OkFrameAdapter(frame, self.ok_page)
                self.page = self._adapter  # type: ignore[assignment]
                return self.is_authenticated()
        return False

    def is_authenticated(self) -> bool:
        text = self.body_text()
        if "Вход для игроков" in text:
            return False
        markers = ("Мой герой", "Мой клан", "Дуэли", "Башня призраков", "Задания",
                   "Сражения", "Торговля")
        return any(marker in text for marker in markers)

    # ------------------------------------------------------------------ навигация
    def goto(self, path: str) -> None:
        """Переход по странице игры с сохранением сессии jsessionid."""
        self.human.pause("page")
        try:
            self.p.goto(path, wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001
            print(f"[ОК] переход не удался ({path}): {exc}")
            return
        self._settle()
        self.human.maybe_scroll(self.p)
