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
     jsessionid, а относительные пути разрешает от корня сайта — так же,
     как это делает обычный Game на barbars.ru;
  2) OkGame — установка handshake с ОК и поиск кадра игры. ОК периодически
     пересоздаёт игровой iframe, поэтому кадр ищется заново при каждом
     обращении, а «зависший» переход повторяется на свежем кадре;
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
    """Принимает base64(gzip(json)) либо готовый JSON с cookie.

    Сектет в CI может прийти с BOM или лишними переводами строк — поэтому
    чистим строку перед разбором и дополняем base64 до кратности 4.
    """
    raw = (raw or "").strip().lstrip("\ufeff").strip()
    if not raw:
        return [], IPHONE_UA
    if raw.startswith("{"):
        payload = json.loads(raw)
    else:
        raw = raw.replace("\n", "").replace("\r", "")
        raw += "=" * (-len(raw) % 4)
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
    """Кадр игры как «страница»: методы те же, что у Page, но с учётом сессии.

    Кадр берётся не один раз, а у игры: ОК периодически пересоздаёт iframe,
    и старый объект Frame после этого отваливается (навигация по нему виснет
    до таймаута). Поэтому каждый запрос адреса идёт через OkGame.current_frame.
    """

    def __init__(self, game: "OkGame"):
        self._game = game

    # -------------------------------------------------------------- состояние кадра
    @property
    def frame(self) -> Frame:
        return self._game.current_frame()

    @property
    def page(self) -> Page:
        return self._game.ok_page  # type: ignore[return-value]

    @property
    def url(self) -> str:
        return self._game.current_url()

    def title(self) -> str:
        """Заголовок страницы (у Playwright Page это метод, а не свойство)."""
        try:
            return self.frame.title()
        except Exception:  # noqa: BLE001
            return ""

    def is_closed(self) -> bool:
        try:
            return self.frame.is_detached()
        except Exception:  # noqa: BLE001
            return True

    @property
    def jsessionid(self) -> str:
        """Java-сессия игры: ищем в HTML кадра, потом в его URL."""
        return self._game.jsessionid

    # -------------------------------------------------------------- навигация
    def _resolve(self, url: str) -> str:
        """Собрать абсолютный URL так, чтобы сохранить jsessionid."""
        url = OkGame._to_ok_host(url)
        sid = self.jsessionid
        if sid and "jsessionid=" not in url and url.startswith(GAME_HOST):
            url = f"{url};jsessionid={sid}"
        return url

    def goto(self, url: str, wait_until: str = "domcontentloaded", **kwargs: Any) -> Any:
        return self._game.goto_frame(url, wait_until=wait_until, **kwargs)

    def reload(self, **kwargs: Any) -> Any:
        """У Frame нет reload() — просто переходим на текущий адрес заново."""
        url = self.url
        if not url:
            return None
        wait_until = kwargs.pop("wait_until", "domcontentloaded")
        return self._game.goto_frame(url, wait_until=wait_until, **kwargs)

    def wait_for_load_state(self, state: str = "load", **kwargs: Any) -> Any:
        return self.frame.wait_for_load_state(state, **kwargs)

    # -------------------------------------------------------------- чтение
    def content(self) -> str:
        return self.frame.content()

    def inner_text(self, selector: str, **kwargs: Any) -> str:
        return self.frame.inner_text(selector, **kwargs)

    def text_content(self, selector: str, **kwargs: Any) -> str | None:
        return self.frame.text_content(selector, **kwargs)

    def locator(self, selector: str, **kwargs: Any) -> Any:
        return self.frame.locator(selector, **kwargs)

    def query_selector(self, selector: str, **kwargs: Any) -> Any:
        return self.frame.query_selector(selector, **kwargs)

    def query_selector_all(self, selector: str, **kwargs: Any) -> Any:
        return self.frame.query_selector_all(selector, **kwargs)

    def title_text(self) -> str:
        return self.title()

    # -------------------------------------------------------------- ввод
    def fill(self, selector: str, value: str, **kwargs: Any) -> Any:
        return self.frame.locator(selector).fill(value, **kwargs)

    def click(self, selector: str, **kwargs: Any) -> Any:
        return self.frame.locator(selector).click(**kwargs)

    def select_option(self, selector: str, value: Any = None, **kwargs: Any) -> Any:
        return self.frame.locator(selector).select_option(value, **kwargs)

    def check(self, selector: str, **kwargs: Any) -> Any:
        return self.frame.locator(selector).check(**kwargs)

    def uncheck(self, selector: str, **kwargs: Any) -> Any:
        return self.frame.locator(selector).uncheck(**kwargs)

    def press(self, selector: str, key: str, **kwargs: Any) -> Any:
        return self.frame.locator(selector).press(key, **kwargs)

    # -------------------------------------------------------------- прочее
    def mouse(self) -> Any:
        """Мышь — у главной страницы (координаты кадра считаются от неё)."""
        return self.page.mouse

    def keyboard(self) -> Any:
        return self.page.keyboard

    def screenshot(self, **kwargs: Any) -> Any:
        return self.page.screenshot(**kwargs)

    def evaluate(self, expression: str, **kwargs: Any) -> Any:
        return self.frame.evaluate(expression, **kwargs)

    def frames(self) -> list[Frame]:
        return [self.frame]


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
        self._frame_ref: Frame | None = None
        self._jsessionid: str = ""
        self._last_url: str = ""

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

    # ------------------------------------------------------------------ кадр игры
    def current_frame(self) -> Frame:
        """Текущий кадр с игрой (переищется, если ОК пересоздал iframe)."""
        frame = self._frame_ref
        if frame is not None:
            try:
                if not frame.is_detached():
                    return frame
            except Exception:  # noqa: BLE001
                pass
        frame = self._find_frame()
        if frame is None:
            raise GameError("Кадр игры ОК потерян")
        self._frame_ref = frame
        return frame

    def _find_frame(self, tries: int = 1, wait: int = 3) -> Frame | None:
        """Найти кадр с игрой: сначала по хосту, потом по маркерам содержимого."""
        assert self.ok_page is not None
        for i in range(tries):
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
            if i + 1 < tries:
                time.sleep(wait)
        return None

    def current_url(self) -> str:
        """URL текущей страницы игры (кадр мог потерять URL при пересоздании)."""
        try:
            url = self.current_frame().url
        except Exception:  # noqa: BLE001
            url = ""
        return url or self._last_url

    @property
    def jsessionid(self) -> str:
        """Java-сессия игры (из URL страницы, иначе — из HTML кадра)."""
        if self._jsessionid:
            return self._jsessionid
        try:
            frame = self.current_frame()
        except Exception:  # noqa: BLE001
            return ""
        m = JSESSION_RE.search(frame.url)
        if not m:
            try:
                m = JSESSION_RE.search(frame.content())
            except Exception:  # noqa: BLE001
                m = None
        if m:
            self._jsessionid = m.group(1)
        return self._jsessionid

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
        self._frame_ref = frame
        self._adapter = OkFrameAdapter(self)  # type: ignore[assignment]
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
            frame = self._find_frame()
            if frame is not None:
                self._frame_ref = frame
                return frame
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
                self._frame_ref = frame
                self._adapter = OkFrameAdapter(self)  # type: ignore[assignment]
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

    # ------------------------------------------------------------------ клики
    def _click_selector(self, selector: str, timeout: int = 8000,
                        nth: int = 0) -> bool:
        """Клик с повтором: ОК иногда пересоздаёт игровой iframe, и клик по
        старому кадру не срабатывает — тогда кадр ищем заново и кликаем ещё раз.
        """
        for _ in range(2):
            try:
                locator = self.p.locator(selector)
                count = locator.count()
                if count == 0:
                    return False
                target = locator.nth(min(nth, count - 1))
                target.scroll_into_view_if_needed(timeout=3000)
                self.human.move_mouse_to(self.p, target)
                target.click(timeout=timeout)
                return True
            except Exception as exc:  # noqa: BLE001
                head = str(exc).splitlines()[0][:140]
                print(f"[ОК] клик не сработал: {head}")
                self._frame_ref = None  # кадр мог отвалиться — ищем новый
                time.sleep(1.0)
        return False

    def use_ability(self, href: str) -> bool:
        """Применить умение боя (ссылка с abilityCombatPanel)."""
        if not href:
            return False
        if not self._click_selector("a[href*='" + href + "']"):
            return False
        self._settle()
        self.human.pause("fight")
        return True

    def click_attack(self) -> bool:
        """Кликнуть по основной боевой кнопке ('Бить ...' / 'Атаковать ...')."""
        for label in ("Бить", "Атаковать", "Жечь", "Ударить"):
            selector = f"a:has-text('{label}'), button:has-text('{label}')"
            if self._click_selector(selector):
                self._settle()
                self.human.pause("fight")
                return True
        return False

    def click_text(self, text: str, *, exact: bool = False, nth: int = 0,
                   tags: tuple[str, ...] = ("a", "button", "input"),
                   timeout: int = 8000) -> bool:
        """Кликнуть по элементу с указанным текстом (с повтором на новом кадре)."""
        for tag in tags:
            selectors: list[str] = []
            if exact:
                selectors.append(f"{tag}[value='{text}']")
                selectors.append(f"{tag}:text-is('{text}')")
            else:
                selectors.append(f"{tag}:text-is('{text}')")
                selectors.append(f"{tag}:has-text('{text}')")
            for sel in selectors:
                if self._click_selector(sel, timeout=timeout, nth=nth):
                    self._settle()
                    self.human.pause("action")
                    return True
        return False

    # ------------------------------------------------------------------ навигация
    def goto(self, path: str) -> None:
        """Переход по странице игры с сохранением сессии jsessionid.

        Агент ходит по абсолютным адресам вида https://barbars.ru/game/towers —
        в канале ОК это другой хост (od.barbars.ru) и нужна jsessionid,
        поэтому адрес переписывается, а сессия добавляется адаптером.
        """
        self.human.pause("page")
        url = self._to_ok_host(path)
        ok = self.goto_frame(url)
        if not ok:
            return
        self._settle()
        self.human.maybe_scroll(self.p)

    def goto_frame(self, url: str, wait_until: str = "domcontentloaded",
                   timeout: int = 45_000, **kwargs: Any) -> bool:
        """Переход внутри кадра игры с повтором на свежем кадре.

        ОК периодически пересоздаёт игровой iframe: если переход пришёлся на
        этот момент, Playwright ждёт до таймаута и страница не открывается.
        Поэтому при неудаче кадр ищется заново и переход повторяется.
        """
        target = self._resolve_jsession(url)
        for attempt in range(2):
            try:
                frame = self.current_frame()
                frame.goto(target, wait_until=wait_until, timeout=timeout, **kwargs)
            except Exception as exc:  # noqa: BLE001
                print(f"[ОК] переход не удался ({url}): {exc}")
                self._frame_ref = None  # кадр мог отвалиться — ищем новый
                frame = self._find_frame(tries=4, wait=3)
                if frame is None:
                    return False
                self._frame_ref = frame
                continue
            self._last_url = target
            m = JSESSION_RE.search(target)
            if m:
                self._jsessionid = m.group(1)
            return True
        return False

    def _resolve_jsession(self, url: str) -> str:
        """Дописать jsessionid, если его ещё нет в адресе."""
        if "jsessionid=" in url or not url.startswith(GAME_HOST):
            return url
        sid = self.jsessionid
        if not sid:
            return url
        head, sep, tail = url.partition("?")
        return f"{head};jsessionid={sid}{sep}{tail}"

    @staticmethod
    def _to_ok_host(path: str) -> str:
        """Переписать адрес игры на хост ОК.

        Как и обычный Game на barbars.ru: относительные пути разрешаются
        от корня сайта, ;jsessionid= выбрасывается (его добавит адаптер).
        """
        path = re.sub(r";jsessionid=[0-9A-Za-z]+", "", path)
        if path.startswith("https://barbars.ru"):
            return GAME_HOST + path[len("https://barbars.ru"):]
        if path.startswith("http"):
            return path
        return urljoin(GAME_HOST + "/", path)
