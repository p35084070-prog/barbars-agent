"""Драйвер игры «Варвары» (barbars.ru) поверх Playwright.

Слой доступа: навигация, чтение состояния, безопасные клики по тексту.
Никакой бизнес-логики здесь нет — она в rules.py.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import Page, TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from .humanize import Humanizer

BASE_URL = "https://barbars.ru/"

# Числовые значения в игре используют суффиксы: 52k = 52000, 1.5M = 1500000
_NUM_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*([kKmMgG]?)")

# Блок вещи в рюкзаке/сундуке: `item/id/2093162597"><span>Сапоги Атланта</span>`
NAME_BLOCK_RE = re.compile(r"item/id/(\d+)\"><span>([^<]{2,60})</span>", re.S)

# Игра маскирует часть букв латинскими омоглифами: «Версерк» -> «Bepcepк»,
# «готово» -> «гoтoво». Для сравнения приводим латиницу к кириллице.
_HOMOGLYPHS = str.maketrans(
    {
        "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у",
        "k": "к", "m": "м", "t": "т", "b": "в", "h": "н",
    }
)


def normalize_ru(text: str) -> str:
    """Латинские омоглифы -> кириллица (для сравнения строк игры)."""
    return text.translate(_HOMOGLYPHS).lower()


def parse_amount(raw: str | None) -> int:
    """'1.96M' -> 1960000, '52k' -> 52000, '290' -> 290."""
    if not raw:
        return 0
    raw = raw.strip().replace("\u00a0", " ").replace(" ", "")
    m = _NUM_RE.search(raw)
    if not m:
        return 0
    value = float(m.group(1).replace(",", "."))
    suffix = m.group(2).lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    elif suffix == "g":
        value *= 1_000_000_000
    return int(value)


def parse_master_page(html: str) -> dict[str, Any]:
    """Разбор страницы /user/master: цены параметров и цена уровня мастерства.

    Возвращает:
      {"params": [{"param": "strength", "cost": 100, "gain": 24,
                   "currency": "gold", "href": ...}],
       "mastery": {"iron": 3000, "mifril": 200}}

    В разметке иконка валюты лежит рядом с числом: `<img ... money_gold.png><span>100</span>`.
    Тег `<img>` в игре закрывается без слэша (`<img ...>`), поэтому в регулярках
    нельзя писать `/>` — иначе цены не читаются и прокачка молча не работает.
    """
    params: list[dict[str, Any]] = []
    for m in re.finditer(r"moreParamsPanel:(\w+):upBlock:upLink", html):
        segment = html[m.end():m.end() + 400]
        # валюта стоимости: иконка сразу после «за»
        cost_m = re.search(
            r"за\s*<span[^>]*>\s*<img[^>]*icons/(\w+)\.png[^>]*>\s*<span>([\d.,]+[KkMm]?)</span>",
            segment,
        )
        if not cost_m:
            continue
        gain_m = re.search(r"\+[^0-9]{0,40}(\d+)", segment)
        currency = {
            "money_gold": "gold",
            "money_silver": "silver",
            "ironbar": "iron",
            "mifrilbar": "mifril",
            "silverbar": "silver",
        }.get(cost_m.group(1), cost_m.group(1))
        params.append(
            {
                "param": m.group(1),
                "cost": parse_amount(cost_m.group(2)),
                "gain": int(gain_m.group(1)) if gain_m else 1,
                "currency": currency,
                "href": f"moreParamsPanel:{m.group(1)}:upBlock:upLink",
            }
        )
    mastery: dict[str, int] = {}
    m = re.search(r"upgradeLink", html)
    if m:
        segment = html[m.start():m.start() + 500]
        for icon, number in re.findall(
            r"icons/(ironbar|mifrilbar|money_\w+)\.png[^>]*>\s*<span>([\d.,]+[KkMm]?)</span>",
            segment,
        ):
            key = {"ironbar": "iron", "mifrilbar": "mifril", "money_gold": "gold"}.get(icon, icon)
            mastery[key] = parse_amount(number)
    return {"params": params, "mastery": mastery}


@dataclass
class Status:
    """Топ-панель: здоровье, энергия, золото, серебро, железо, мифрил, бутылки."""

    hp: int | None = None
    energy: int | None = None
    gold: int | None = None
    silver: int | None = None
    iron: int | None = None
    mifril: int | None = None
    bottles: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "hp": self.hp,
            "energy": self.energy,
            "gold": self.gold,
            "silver": self.silver,
            "iron": self.iron,
            "mifril": self.mifril,
            "bottles": self.bottles,
        }


@dataclass
class Hero:
    level: int | None = None
    klass: str | None = None
    guild_id: int | None = None
    guild_name: str | None = None
    xp_cur: int | None = None
    xp_need: int | None = None
    participation: int | None = None
    talent_points: int | None = None
    talents_spent: int | None = None
    mastery: str | None = None
    profession: str | None = None
    max_energy: int | None = None
    max_hp: int | None = None


@dataclass
class CombatState:
    """Снимок боевой страницы."""

    title: str = ""
    our_hp: int | None = None
    our_energy: int | None = None
    enemy_hp: int | None = None
    enemy_name: str = ""
    attack_links: list[str] = field(default_factory=list)
    abilities: list[dict[str, Any]] = field(default_factory=list)
    heal_links: list[str] = field(default_factory=list)
    flee_links: list[str] = field(default_factory=list)
    potion_links: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    finished: bool = False
    victory: bool | None = None


class GameError(RuntimeError):
    pass


def clean_credential(value: str) -> str:
    """Убрать BOM и прочие невидимые символы из строки учётных данных.

    Файл с учётными данными может прийти с UTF-8 BOM (например, после
    пересборки в PowerShell) — иначе логин уходит в игру как '\ufeffник'
    и она отвечает «Неверный ник или пароль».
    """
    return value.strip().lstrip("\ufeff").strip()


class Game:
    """Обёртка над страницей браузера."""

    def __init__(self, config: dict[str, Any], profile_dir: str | Path):
        self.config = config
        self.base_url = config.get("base_url", BASE_URL)
        self.profile_dir = str(Path(profile_dir).resolve())
        self.page: Page | None = None
        self._playwright = None
        self._context = None
        self.hero_id: int | None = None
        self.guild_id: int | None = None
        self.human = Humanizer(config.get("humanize"))
        self.headless = bool(config.get("headless", False))
        self.credentials = self._load_credentials(config)

    # ------------------------------------------------------------------ lifecycle

    def start(self, headless: bool | None = None) -> None:
        if self.page is not None:
            return
        headless = self.config.get("headless", False) if headless is None else headless
        self.headless = bool(headless)
        Path(self.profile_dir).mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            self.profile_dir,
            headless=headless,
            viewport={"width": 640, "height": 900},
            locale="ru-RU",
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context.set_default_timeout(20_000)
        self.page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def close(self) -> None:
        """Закрыть браузер. Всегда обнуляем состояние.

        Если оборвалось соединение, `context.close()`/`playwright.stop()` падают —
        из-за этого раньше `self.page` оставался старым объектом, и перезапуск
        браузера не стартовал (`start()` выходит, если страница уже есть).
        """
        try:
            if self._context:
                try:
                    self._context.close()
                except Exception:
                    pass
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
        finally:
            self._context = None
            self._playwright = None
            self.page = None

    def __enter__(self) -> "Game":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ navigation

    @property
    def p(self) -> Page:
        if self.page is None:
            raise GameError("Браузер не запущен")
        return self.page

    def goto(self, path: str) -> None:
        """Переход по URL. path может быть абсолютным или относительным."""
        path = re.sub(r";jsessionid=[0-9A-Za-z]+", "", path)
        url = path if path.startswith("http") else urljoin(self.base_url, path)
        self.human.pause("page")
        self.p.goto(url, wait_until="domcontentloaded")
        self._settle()
        self.human.maybe_scroll(self.p)

    def _settle(self, timeout: int = 2500) -> None:
        """Дождаться, пока Wicket дорисует страницу."""
        try:
            self.p.wait_for_load_state("networkidle", timeout=timeout)
        except PWTimeout:
            pass
        time.sleep(0.2)

    def reload(self) -> None:
        self.p.reload(wait_until="domcontentloaded")
        self._settle()

    def body_text(self) -> str:
        try:
            return self.p.inner_text("body")
        except PWTimeout:
            return ""

    # ------------------------------------------------------------------ primitives

    def click_text(
        self,
        text: str,
        *,
        exact: bool = False,
        nth: int = 0,
        tags: tuple[str, ...] = ("a", "button", "input"),
        timeout: int = 8000,
    ) -> bool:
        """Кликнуть по элементу с указанным текстом. False — не нашли."""
        for tag in tags:
            selectors = []
            if exact:
                selectors.append(f"{tag}[value='{text}']")
                selectors.append(f"{tag}:text-is('{text}')")
            else:
                selectors.append(f"{tag}:text-is('{text}')")
                selectors.append(f"{tag}:has-text('{text}')")
            for sel in selectors:
                locator = self.p.locator(sel)
                count = locator.count()
                if count == 0:
                    continue
                index = min(nth, count - 1)
                target = locator.nth(index)
                try:
                    target.scroll_into_view_if_needed(timeout=3000)
                    self.human.move_mouse_to(self.p, target)
                    self.human.pause("action")
                    target.click(timeout=timeout)
                except PWTimeout:
                    continue
                except Exception:
                    continue
                self._settle()
                self.human.pause("action")
                self.human.maybe_long_pause()
                return True
        return False

    def click_href(self, pattern: str, *, nth: int = 0) -> bool:
        locator = self.p.locator(f"a[href*='{pattern}']")
        if locator.count() == 0:
            return False
        target = locator.nth(min(nth, locator.count() - 1))
        try:
            target.scroll_into_view_if_needed(timeout=3000)
            self.human.move_mouse_to(self.p, target)
            self.human.pause("action")
            target.click(timeout=8000)
        except Exception:
            return False
        self._settle()
        self.human.pause("action")
        return True

    def link_texts(self) -> list[str]:
        return [t.strip() for t in self.p.locator("a").all_inner_texts() if t.strip()]

    def has_attack(self) -> bool:
        """Есть ли на странице кнопка удара («Бить ...» / «Бить врагов»)."""
        return self.p.locator("a:has-text('Бить'), button:has-text('Бить')").count() > 0

    def claim_daily_award(self) -> bool:
        """Ежедневная награда на главной (ссылка awardLink).

        У новых героев это даёт бесплатный бой в подземелье («Забытый склеп
        остался 1 бой»), у старших — дополнительные бонусы.
        """
        self.goto("https://barbars.ru/")
        return self.click_href("awardLink")

    def open_tower(self) -> str | None:
        """Открыть первую доступную локацию башни (/game/towers).

        Бой на башне бесплатный и длительный: капает опыт, железо, бутылочки
        и выпадают вещи. Возвращает название локации либо None.
        """
        self.goto("https://barbars.ru/game/towers")
        locator = self.p.locator("a[href*='locationLink']")
        if locator.count() == 0:
            return None
        target = locator.first
        name = ""
        try:
            name = (target.inner_text() or "").strip()
        except Exception:
            name = ""
        try:
            target.scroll_into_view_if_needed(timeout=3000)
            self.human.move_mouse_to(self.p, target)
            self.human.pause("action")
            target.click(timeout=8000)
        except Exception:
            return None
        self._settle()
        self.human.pause("page")
        return name or "башня"

    def has_text(self, needle: str) -> bool:
        return needle.lower() in self.body_text().lower()

    def is_authenticated(self) -> bool:
        """Авторизован ли текущий браузер (в игре есть герой/клан, нет формы входа)."""
        text = self.body_text()
        if "Вход для игроков" in text:
            return False
        markers = ("Выход", "Мой герой", "Мой клан", "Дуэли", "Башня призраков", "Задания")
        return any(marker in text for marker in markers)

    def wait_for_login(self, timeout_sec: int = 600, poll_sec: float = 3.0) -> bool:
        """Ждать ручной авторизации в открытом окне браузера."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.is_authenticated():
                return True
            # пользователь мог уже ввести логин/пароль — пробуем автовход ещё раз
            if self.credentials and self.auto_login():
                return True
            time.sleep(poll_sec)
        return self.is_authenticated()

    # ------------------------------------------------------------------ авторизация

    def _load_credentials(self, config: dict[str, Any]) -> tuple[str, str] | None:
        """Логин/пароль из локального файла или переменных окружения.

        Никогда не храним пароль в config.json и не просим его в чате:
        файл `credentials.txt` рядом с конфигом или переменные BARBARS_USER/BARBARS_PASS.
        """
        import os

        auth = config.get("auth", {})
        user = os.environ.get(auth.get("username_env", "BARBARS_USER"), "").strip()
        password = os.environ.get(auth.get("password_env", "BARBARS_PASS"), "").strip()
        if not (user and password):
            raw_file = auth.get("credentials_file", "credentials.txt")
            path = self._credentials_file(raw_file)
            if path.exists():
                raw = path.read_text(encoding="utf-8-sig")
                lines = [clean_credential(line) for line in raw.splitlines()]
                lines = [line for line in lines if line]
                if len(lines) >= 2:
                    user = user or lines[0]
                    password = password or lines[1]
            else:
                print(f"[вход] файл учётных данных не найден: {path}")
        if user and password:
            return user, password
        return None

    def _credentials_file(self, raw: str) -> Path:
        """Где искать файл учётных данных.

        Путь в конфиге может быть относительным: сначала пробуем относительно
        каталога конфига, затем относительно корня репозитория (в облаке
        конфиги лежат в deploy/, а файл — в корне).
        """
        path = Path(raw)
        if path.is_absolute():
            return path
        candidates = []
        root = self.config.get("_root")
        if root:
            candidates.append(Path(root) / path)
        repo_root = Path(__file__).resolve().parents[1]
        candidates.append(repo_root / path)
        candidates.append(Path.cwd() / path)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def auto_login(self) -> bool:
        """Войти автоматически, если есть сохранённые учётные данные."""
        if not self.credentials:
            return False
        user, password = self.credentials
        try:
            self.goto("https://barbars.ru/login")
            self.p.fill("input[name='login']", user, timeout=8000)
            self.p.fill("input[name='password']", password, timeout=8000)
            self.human.pause("action")
            self.p.click("input[type='submit'], button:has-text('Войти')", timeout=8000)
            try:
                self.p.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            self._settle()
            self.human.pause("page")
        except Exception as exc:
            print(f"[вход] автовход не удался: {exc}")
            return False
        ok = self.is_authenticated()
        if ok:
            print("[вход] автовход выполнен")
            return True
        # диагностика: показываем, что игра ответила вместо входа
        try:
            body = " ".join(self.body_text().split())
        except Exception:
            body = ""
        print(f"[вход] автовход не прошёл, страница: {body[:400]}")
        try:
            self.dump_page("login-failed", self.config.get("_root", "."))
        except Exception:
            pass
        return False

    def browser_alive(self) -> bool:
        """Жив ли ещё браузер (окно могли закрыть, соединение могло умереть).

        `is_closed()` не годится: если умер сам процесс браузера, страница может
        считаться «не закрытой», и агент продолжит работать с мёртвым соединением
        (Playwright будет сыпать «Playwright connection closed»). Поэтому
        дополнительно делаем дешёвую живую проверку — title() обращается к
        соединению и падает, если оно мертво.
        """
        try:
            if self.page is None or self.page.is_closed():
                return False
            self.page.title()
            return True
        except Exception:
            return False

    def _kill_stale_browsers(self) -> None:
        """Убить осиротевшие процессы Chrome, держащие наш профиль.

        Иначе Chromium вместо запуска показывает диалог «профиль занят»
        и Playwright падает с ошибкой запуска.
        """
        import subprocess

        profile = self.profile_dir.replace("\\", "\\\\")
        script = (
            "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{profile}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                timeout=60,
            )
        except Exception:
            pass

    def restart(self, headless: bool | None = None) -> bool:
        """Перезапустить браузер и снова войти в игру.

        Сначала снимаем блокировку профиля, затем пробуем несколько раз —
        Windows иногда держит lock ещё пару секунд после смерти процесса.
        """
        try:
            self.close()
        except Exception:
            pass
        last_error = ""
        for attempt in range(1, 4):
            self._kill_stale_browsers()
            time.sleep(3 + attempt * 2)
            try:
                self.start(headless=headless)
            except Exception as exc:
                last_error = str(exc).splitlines()[0]
                print(f"[перезапуск] попытка {attempt}: {last_error}")
                continue
            try:
                if self.ensure_login(timeout_sec=300):
                    print("[перезапуск] браузер поднят, сессия активна")
                    return True
            except Exception as exc:
                last_error = str(exc).splitlines()[0]
            print(f"[перезапуск] попытка {attempt}: вход не завершён")
        print(f"[перезапуск] не удалось: {last_error}")
        return False

    def ensure_login(self, timeout_sec: int = 600) -> bool:
        """Если не авторизован — автовход, иначе ждём ручной вход пользователем."""
        self.goto("https://barbars.ru/")
        if self.is_authenticated():
            return True
        if self.auto_login():
            return True
        if self.headless:
            # в облаке/без окна ждать ручной вход бессмысленно — выходим сразу
            print("[вход] автовход не удался, а браузер без окна — продолжать нечем")
            return False
        print("[вход] Сессия не активна: войди в игру в открытом окне браузера.")
        return self.wait_for_login(timeout_sec=timeout_sec)

    # ------------------------------------------------------------------ parsing

    def status(self) -> Status:
        st = Status()
        st.hp = self._icon_value(["life.png", "lifealert.gif", "lifealt.gif"])
        st.energy = self._icon_value(["energy.png"])
        # ресурсы берём из блока «ресурсы» в шапке: иконка железа ещё встречается
        # в других местах (например, «разобрать на 281» у нового предмета),
        # и первый попавшийся элемент давал не баланс, а чужое число
        st.gold = self._resource_value("money_gold.png")
        st.silver = self._resource_value("money_silver.png")
        st.iron = self._resource_value("ironbar.png")
        st.mifril = self._resource_value("mifrilbar.png")
        st.bottles = self._resource_value("bottle.png")
        return st

    def _resource_value(self, icon: str) -> int | None:
        """Счётчик ресурса из блока ресурсов в шапке.

        Блок ищем по бутылочке (bottle.png) — он есть всегда, когда виден
        счётчик. Иконка железа встречается и в других местах (например,
        «разобрать на 225» у только что полученного предмета), и первый
        попавшийся элемент давал не баланс, а чужое число.
        """
        try:
            raw = self.p.evaluate(
                """icon => {
                    const all = Array.from(document.querySelectorAll('img'));
                    const bottle = all.find(i => (i.getAttribute('src') || '').includes('bottle.png'));
                    if (!bottle) return '';
                    let box = bottle.parentElement;
                    while (box) {
                        const hit = Array.from(box.querySelectorAll('img'))
                            .find(i => (i.getAttribute('src') || '').includes(icon));
                        if (hit) {
                            const span = hit.nextElementSibling;
                            if (span && span.textContent) return span.textContent.trim();
                        }
                        box = box.parentElement;
                    }
                    return '';
                }""",
                icon,
            )
            if raw:
                return parse_amount(str(raw))
        except Exception:
            pass
        return self._icon_value([icon])

    def close_new_item_panel(self) -> bool:
        """Закрыть панель «новый предмет» (после подарка/находки)."""
        return self.click_href("newItemMessageBlock:hideLink")

    def _icon_value(self, icon_names: list[str]) -> int | None:
        """Значение рядом с иконкой: <img src=...><span>123</span>."""
        for icon in icon_names:
            locator = self.p.locator(f"img[src*='{icon}'] + span")
            try:
                if locator.count() == 0:
                    continue
                raw = locator.first.inner_text().strip()
                if raw:
                    return parse_amount(raw)
            except PWTimeout:
                continue
        return None

    def hero(self) -> Hero:
        hero = Hero()
        text = self.body_text()
        # ВАЖНО: над героем висит панель «новый предмет» вида «Штаны 1 ур, новый» —
        # она ломает наивный разбор уровня, поэтому матчим только по классу героя
        # (воин/медик) либо по строке «ник , N ур,».
        m = re.search(r"(\d+)\s*ур,\s*(воин|медик)", text, re.IGNORECASE)
        if m:
            hero.level = int(m.group(1))
            hero.klass = m.group(2).lower()
        if hero.level is None:
            m = re.search(r",\s*(\d+)\s*ур,", text, re.IGNORECASE)
            if m:
                hero.level = int(m.group(1))
        m = re.search(r"уровень:\s*(\d+)", text, re.IGNORECASE)
        if m:
            hero.level = int(m.group(1))
        m = re.search(r"опыт:\s*([\d.,]+[kKmMgG]?)\s*/\s*([\d.,]+[kKmMgG]?)", text, re.IGNORECASE)
        if m:
            hero.xp_cur = parse_amount(m.group(1))
            hero.xp_need = parse_amount(m.group(2))
        m = re.search(r"участие:\s*([\d.,]+[kKmMgG]?)", text, re.IGNORECASE)
        if m:
            hero.participation = parse_amount(m.group(1))
        m = re.search(r"таланты\s*\((\d+)\s*/\s*(\d+)\)", text, re.IGNORECASE)
        if m:
            hero.talents_spent = int(m.group(1))
        m = re.search(r"энергия:\s*(\d+)", text, re.IGNORECASE)
        if m:
            hero.max_energy = int(m.group(1))
        m = re.search(r"здоровье:\s*(\d+)", text, re.IGNORECASE)
        if m:
            hero.max_hp = int(m.group(1))
        m = re.search(r"профессия:\s*([^\n]+)", text, re.IGNORECASE)
        if m:
            hero.profession = m.group(1).strip()
        m = re.search(r"мастер\s*\+?([\d.]+)%", text, re.IGNORECASE)
        if m:
            hero.mastery = m.group(1) + "%"
        m = re.search(r"(\d+)\s*ур,\s*медик", text, re.IGNORECASE)
        if m:
            hero.klass = "медик"
        # id героя и клана — из ссылок вида user/body/id/<id> и guild/<id>
        try:
            body_link = self.p.locator("a[href*='user/body/id/']").first
            hero_id = re.search(r"user/body/id/(\d+)", body_link.get_attribute("href") or "")
            if hero_id:
                self.hero_id = int(hero_id.group(1))
        except Exception:
            pass
        try:
            guild_link = self.p.locator("a[href*='guild/']").first
            guild_id = re.search(r"guild/(\d+)", guild_link.get_attribute("href") or "")
            if guild_id:
                self.guild_id = int(guild_id.group(1))
        except Exception:
            pass
        hero.guild_id = self.guild_id
        return hero

    def talent_points(self) -> int:
        text = self.body_text()
        m = re.search(r"У тебя очков:\s*(\d+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"очков:\s*(\d+)", text, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 0

    def combat(self) -> CombatState:
        """Разбор боевой страницы (башня, дуэль, пещера, арена...)."""
        cs = CombatState()
        cs.title = self.p.title()
        st = self.status()
        cs.our_hp = st.hp
        cs.our_energy = st.energy

        # Здоровье противника — значение рядом с life-иконкой (второе в списке).
        life_values: list[int] = []
        for locator in self.p.locator("img[src*='life'] + span").all():
            try:
                raw = locator.inner_text().strip()
            except Exception:
                continue
            if not raw or raw[0] in "+-":
                continue
            value = parse_amount(raw)
            if value:
                life_values.append(value)
        if len(life_values) >= 2:
            cs.enemy_hp = life_values[1]
        elif life_values:
            cs.enemy_hp = life_values[0]

        # Имя противника — текст ссылки удара вида "Бить <имя>".
        for link in self.p.locator("a").all():
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if not text:
                continue
            if "abilityCombatPanel" in href:
                continue  # это умение, его разбираем отдельно
            flat = text.split("\n")[0].strip()
            if text.startswith(("Бить", "Атаковать", "Ударить", "Напасть", "Жечь")):
                # «Жечь энергию врагам» — тоже боевое действие (осада башни),
                # без него агент не понимает, что бой продолжается
                cs.attack_links.append(flat)
                if text.startswith("Бить"):
                    cs.enemy_name = flat[len("Бить") :].strip()
            elif text.startswith("Лечить"):
                cs.heal_links.append(flat)
            elif text.startswith("Сбежать") or text.startswith("Отступить") or text.startswith("Убежать"):
                cs.flee_links.append(flat)
            elif "бутылочк" in text.lower() or "зелье" in text.lower() or "выпить" in text.lower():
                cs.potion_links.append(flat)

        # Умения: ссылки с abilityCombatPanel в href — их видно на любой боевой странице.
        for link in self.p.locator("a[href*='abilityCombatPanel']").all():
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if not text:
                continue
            ready = "готово" in normalize_ru(text)
            name = text.split("(")[0].strip().split("\n")[0].strip()
            desc = ""
            m = re.search(
                r"(увеличивает урон|уменьшает урон|уворот от удара|восстанавливает[^\n]*|энерг[^\n]*)",
                normalize_ru(text),
            )
            if m:
                desc = m.group(1).lower()
            cs.abilities.append({"name": name, "text": text, "ready": ready, "desc": desc, "href": href})

        # Лог боя — последние строки вида "Ты ударил ... на 2403 крит".
        for line in self.body_text().splitlines():
            line = line.strip()
            if re.search(r"Ты\s+(удар|убил|вылечил|исцелил|включил|промах|получил|атаку)", line):
                cs.log_lines.append(line)
        cs.log_lines = cs.log_lines[-8:]

        body = self.body_text()
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        tail = "\n".join(lines[-12:])
        cs.finished = bool(re.search(r"Победа|Поражение|Награда за победу|бой окончен", tail, re.IGNORECASE))
        if re.search(r"Поражение|ты погиб|ты убит|ты проиграл", tail, re.IGNORECASE):
            cs.victory = False
        elif re.search(r"Победа|ты победил|побеждён", tail, re.IGNORECASE):
            cs.victory = True
        elif not cs.attack_links and not cs.abilities and cs.log_lines:
            # боевых кнопок нет — бой закончился
            cs.finished = True
        return cs

    def fight_limits(self) -> dict[str, int]:
        """Сколько бесплатных боёв осталось: {'dungeon': n, 'duel': m}.

        Лимиты видны на главной ссылками вида «Подземелья осталось 1 бой».
        ВНИМАНИЕ: на `/fightmore` есть «Открыть всё за 50» — это платная
        покупка боёв (серебро/золото), её бесплатные лимиты НЕ считаем.
        """
        limits: dict[str, int] = {}
        text = self.body_text()
        for name, count in re.findall(r"([^\n]*?)\s+осталось\s*(\d+)\s*бо", text):
            key = name.strip().lower()
            if "дуэл" in key:
                limits["duel"] = int(count)
            elif "башн" in key or "подзем" in key or "пещер" in key:
                limits["dungeon"] = int(count)
            else:
                limits.setdefault(key, int(count))
        return limits

    def fight_timers(self) -> dict[str, int]:
        """Через сколько минут откроются бесплатные подземелья и дуэли.

        На главной: «Подземелья откроются через 13мин. 19сек.». Если
        подземелья уже открыты (таймера нет) — возвращаем 0.
        """
        out: dict[str, int] = {}
        text = " ".join(self.body_text().split())
        for key, pat in (
            ("dungeon", r"Подземелья откроются через\s*(\d+)\s*мин"),
            ("duel", r"Дуэли откроются через\s*(\d+)\s*мин"),
        ):
            m = re.search(pat, text, re.IGNORECASE)
            out[key] = int(m.group(1)) if m else 0
        return out

    # ------------------------------------------------------------------ actions

    def repair_all(self) -> bool:
        """Починить снаряжение железом.

        На странице бывает и «Починить все вещи за N», и отдельные ссылки
        «Починить <вещь> за N» — если вещь сломана, кнопки «Починить все»
        может не быть вовсе. Поэтому чиним по очереди все найденные ссылки.
        """
        repaired = False
        for _ in range(25):
            locator = self.p.locator(
                "a:has-text('Починить'), button:has-text('Починить')")
            if locator.count() == 0:
                break
            try:
                locator.first.scroll_into_view_if_needed(timeout=3000)
                locator.first.click(timeout=8000)
            except Exception:
                break
            self._settle()
            repaired = True
        return repaired

    def take_clan_quest(self, index: int = 0) -> bool:
        """Взять клановое задание по порядковому номеру.

        После клика проверяем страницу: задание считается взятым, если
        появилось «Выполняет: <ник>» — клик иногда проходит, но ответ
        приходит слишком поздно и клик выглядит неудачным.
        """
        locator = self.p.locator("a:has-text('Взять задание'), button:has-text('Взять задание')")
        if locator.count() == 0:
            return False
        try:
            locator.nth(min(index, locator.count() - 1)).click(timeout=8000)
        except Exception:
            pass
        self._settle()
        try:
            if "Выполняет:" in self.body_text():
                return True
        except Exception:
            pass
        return True

    def cancel_clan_quest(self) -> bool:
        """Отменить текущее задание («Отменить задание»)."""
        locator = self.p.locator(
            "a:has-text('Отменить задание'), button:has-text('Отменить задание')")
        if locator.count() == 0:
            return False
        try:
            locator.first.click(timeout=8000)
        except Exception:
            return False
        self._settle()
        return True

    def spend_talent(self, talent_name: str) -> tuple[bool, str]:
        """Потратить очко таланта.

        На /user/stances талант — ссылка на /user/talent/0/<id>, а на той странице
        есть кнопка «выучить за N». Возвращает (успех, описание).
        """
        if "/user/stances" not in self.p.url:
            self.goto("user/stances")

        def find_talent_link() -> Any:
            for a in self.p.locator("a[href*='/user/talent']").all():
                try:
                    if (a.inner_text() or "").strip() == talent_name:
                        return a
                except Exception:
                    continue
            return None

        link = find_talent_link()
        if link is None:
            # ветки специализаций: открываем категорию и ищем внутри
            for a in self.p.locator("a[href*='/user/talents/']").all():
                href = a.get_attribute("href")
                if not href:
                    continue
                self.goto(href)
                link = find_talent_link()
                if link is not None:
                    break
        if link is None:
            return False, "талант не найден"

        href = link.get_attribute("href")
        if href:
            self.goto(href)
        for a in self.p.locator("a").all():
            try:
                text = (a.inner_text() or "").strip()
            except Exception:
                continue
            m = re.search(r"выучить\s+за\s+(\d+)", text, re.IGNORECASE)
            if not m:
                continue
            cost = int(m.group(1))
            try:
                a.click(timeout=8000)
            except Exception:
                return False, "клик по кнопке «выучить» не удался"
            self._settle()
            return True, f"выучено за {cost} очко(ов)"
        return False, "кнопка «выучить» не найдена"

    def use_ability(self, href: str) -> bool:
        locator = self.p.locator(f"a[href*='{href}']")
        if locator.count() == 0:
            return False
        target = locator.first
        try:
            target.scroll_into_view_if_needed(timeout=3000)
            self.human.move_mouse_to(self.p, target)
            self.human.pause("fight")
            target.click(timeout=8000)
        except Exception:
            return False
        self._settle()
        self.human.pause("fight")
        return True

    def click_attack(self) -> bool:
        """Кликнуть по основной боевой кнопке ('Бить ...' / 'Атаковать ...')."""
        for label in ("Бить", "Атаковать", "Жечь", "Ударить"):
            locator = self.p.locator(f"a:has-text('{label}'), button:has-text('{label}')")
            if locator.count() == 0:
                continue
            target = locator.first
            try:
                target.scroll_into_view_if_needed(timeout=3000)
                self.human.move_mouse_to(self.p, target)
                self.human.pause("fight")
                target.click(timeout=8000)
            except Exception:
                continue
            self._settle()
            self.human.pause("fight")
            return True
        return False

    def donate_clan(self, kind: str = "iron", amount: int | None = None) -> int | None:
        """Вложить ресурсы в хранилище клана.

        Страница: guild/storage/0/<guildId> -> «Добавить железо» -> пресеты
        «Добавить 1000 / 5000 / 10000 / 50000 / 500000 железа».
        Возвращает вложенное количество либо None.
        """
        if not self.guild_id:
            return None
        self.goto(f"guild/storage/0/{self.guild_id}")
        opener = {
            "iron": "Добавить железо",
            "stone": "Добавить камни",
            "gold": "Добавить золото",
        }.get(kind, "Добавить железо")
        if not self.click_text(opener):
            return None

        unit = {"iron": "железа", "stone": "камней", "gold": "золота"}.get(kind, "железа")
        best_value, best_locator = None, None
        for link in self.p.locator("a").all():
            try:
                text = link.inner_text().strip()
            except Exception:
                continue
            m = re.search(rf"Добавить\s+([\d\s]+)\s+{unit}", text, re.IGNORECASE)
            if not m:
                continue
            value = parse_amount(m.group(1))
            if amount is not None and value > amount:
                continue
            if best_value is None or value > best_value:
                best_value, best_locator = value, link
        if best_locator is None:
            return None
        try:
            best_locator.click(timeout=8000)
        except Exception:
            return None
        self._settle()
        return best_value

    def ensure_guild_id(self) -> int | None:
        """Узнать id клана, если он ещё не найден (берём из меню «Мой клан»)."""
        if self.guild_id:
            return self.guild_id
        try:
            if "/user" not in self.p.url:
                self.goto("https://barbars.ru/")
            link = self.p.locator("a[href*='guild/']").first
            match = re.search(r"guild/(\d+)", link.get_attribute("href") or "")
            if match:
                self.guild_id = int(match.group(1))
        except Exception:
            return None
        return self.guild_id

    def activate_altar(self, resource: str = "iron", amount: int | None = None) -> dict[str, Any]:
        """Пожертвовать в алтарь клана (даёт бонус ко всем параметрам).

        На /guild/altar/0/<id> есть варианты «Пожертвовать N»:
          sacrificeIronLink  — пожертвование железом (1250 → +12,5% ко всем параметрам),
          sacrificeMoneyLink — пожертвование деньгами.
        Бонус алтаря протухает примерно через 2,5 часа, поэтому его нужно подновлять.
        """
        result: dict[str, Any] = {"ok": False, "cost": None, "bonus": None, "kind": None}
        guild_id = self.ensure_guild_id()
        if not guild_id:
            print("[алтарь] не удалось определить id клана")
            return result
        self.goto(f"guild/altar/0/{guild_id}")
        for link in self.p.locator("a").all():
            try:
                label = (link.inner_text() or "").strip().replace("\n", " ")
                href = link.get_attribute("href") or ""
                outer = link.evaluate("el => el.outerHTML") or ""
            except Exception:
                continue
            if "sacrifice" not in href.lower() or "Пожертвовать" not in label:
                continue
            if resource == "iron":
                if "ironbar" not in outer:
                    continue
            elif resource == "silver":
                if "money_silver" not in outer or "money_gold" in outer:
                    continue
            else:
                continue
            m = re.search(r"Пожертвовать\s*([\d.,]+)", label)
            cost = parse_amount(m.group(1)) if m else None
            if amount is not None and cost is not None and cost != amount:
                continue
            bm = re.search(r"\+([\d.,]+)\s*%", label)
            bonus = float(bm.group(1).replace(",", ".")) if bm else None
            try:
                self.human.move_mouse_to(self.p, link)
                self.human.pause("action")
                link.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            try:
                link.click(timeout=8000)
            except Exception as exc:
                print(f"[алтарь] обычный клик не удался: {str(exc).splitlines()[0]}")
                try:
                    link.click(timeout=8000, force=True)
                except Exception as exc2:
                    print(f"[алтарь] и форсированный клик не удался: {str(exc2).splitlines()[0]}")
                    return result
            self._settle()
            self.human.pause("page")
            result = {"ok": True, "cost": cost, "bonus": bonus, "kind": resource}
            return result
        return result

    # ------------------------------------------------------------------ магазин снаряжения

    def shop_gear(self, set_name: str = "") -> list[dict[str, Any]]:
        """Товары «Магазина снаряжения» (/trade/auction/shop).

        set_name: "" — набор Берсерка (по умолчанию), "goliaf", "atlant",
        "veteran". Товары 25 уровня мифического качества — то, что нужно
        герою 25+ уровня.
        """
        from . import pages

        url = "https://barbars.ru/trade/auction/shop"
        if set_name:
            url += f"/0/{set_name}"
        self.goto(url)
        return pages.parse_shop_gear(self.p.content())

    def worn_gear(self) -> list[dict[str, str]]:
        """Что надето на герое: [{"name": "Шлем Воина", "slot": "шлем"}, ...]."""
        from . import pages

        url = (
            f"https://barbars.ru/user/body/id/{self.hero_id}"
            if self.hero_id
            else "https://barbars.ru/user/body"
        )
        self.goto(url)
        return pages.parse_worn_gear(self.p.content())

    def other_hero_gear(self, hero_id: str) -> list[dict[str, str]]:
        """Снаряжение другого героя (/user/body/id/<id>) — нужно, чтобы покупать
        ему вещи, которых у него ещё нет."""
        from . import pages

        self.goto(f"https://barbars.ru/user/body/id/{hero_id}")
        return pages.parse_worn_gear(self.p.content())

    def shop_item_price(self, item_id: str) -> tuple[int, int]:
        """(золото, серебро) цены товара магазина — со страницы самого товара."""
        from . import pages

        self.goto(f"https://barbars.ru/trade/auction/shop/item/id/{item_id}")
        return pages.parse_price_text(self.body_text())

    def buy_shop_item_capped(self, item_id: str, max_gold: int = 3) -> tuple[bool, str]:
        """Купить товар магазина, если золота на вещь не больше max_gold.

        Цена проверяется на странице товара («Купить за …»): покупать вслепую
        нельзя — лимит игрока «не больше 3 золота на вещь».
        """
        from . import pages

        self.goto(f"https://barbars.ru/trade/auction/shop/item/id/{item_id}")
        gold, silver = pages.parse_price_text(self.body_text())
        if gold <= 0 and silver <= 0:
            return False, "цену прочитать не удалось — покупать вслепую нельзя"
        if gold > max_gold:
            return False, f"цена {gold} зол. превышает лимит {max_gold} зол."
        if not self.click_href("border:buyoutLink"):
            return False, "кнопка покупки не найдена"
        self.confirm_if_needed()
        self._settle()
        return True, f"куплено за {gold} зол. / {silver} сер."

    def market_lots(self) -> list[dict[str, Any]]:
        """Лоты «Аукциона вещей» (/trade/auction).

        Вход через хаб /trade/auctions: там переключается вкладка «Аукцион вещей»
        (при прямом заходе на /trade/auction открывается главная страница).
        """
        from . import pages

        self.goto("https://barbars.ru/trade/auctions")
        try:
            link = self.p.locator("a:has-text('Аукцион вещей')")
            if link.count():
                link.first.click(timeout=8000)
                self._settle()
        except Exception:
            pass
        if "trade/auction/item/id/" not in (self.p.content() or ""):
            self.goto("https://barbars.ru/trade/auction")
        return pages.parse_market_lots(self.p.content())

    def buy_market_lot(self, item_id: str, pt: int, max_gold: int = 3) -> tuple[bool, str]:
        """Выкупить лот на «Аукционе вещей» (страница лота -> «Выкупить сразу за …»)."""
        from . import pages

        self.goto(f"https://barbars.ru/trade/auction/item/id/{item_id}/pt/{pt}")
        gold, silver = pages.parse_price_text(self.body_text())
        if gold <= 0 and silver <= 0:
            return False, "цену прочитать не удалось"
        if gold > max_gold:
            return False, f"цена {gold} зол. превышает лимит {max_gold} зол."
        if not self.click_href("border:buyoutLink"):
            return False, "кнопка выкупа не найдена"
        self.confirm_if_needed()
        self._settle()
        return True, f"выкуплено за {gold} зол. / {silver} сер."

    def put_on_auction(
        self,
        item_id: str,
        bid_gold: int = 1,
        bid_silver: int = 0,
        buyout_gold: int = 2,
        buyout_silver: int = 0,
    ) -> tuple[bool, str]:
        """Выставить вещь на «Аукцион вещей» (лот: начальная цена и цена выкупа)."""
        self.goto(f"https://barbars.ru/item/id/{item_id}")
        html = self.p.content()
        m = re.search(r'href="([^"]*actionBlock:auctionLink[^"]*)"', html)
        if not m:
            return False, "ссылки «на аукцион» нет (вещь личная или неразрешена)"
        self.goto("https://barbars.ru/" + m.group(1).replace("../../", ""))
        self._settle()
        try:
            self.p.fill("input[name='bidGold']", str(int(bid_gold)), timeout=5000)
            self.p.fill("input[name='bidSilver']", str(int(bid_silver)), timeout=5000)
            self.p.fill("input[name='buyoutGold']", str(int(buyout_gold)), timeout=5000)
            self.p.fill("input[name='buyoutSilver']", str(int(buyout_silver)), timeout=5000)
        except Exception as exc:
            return False, f"поля формы не заполнились: {exc}"
        try:
            self.p.click("input[type='submit'][value='выставить']", timeout=8000)
        except Exception as exc:
            return False, f"кнопка «выставить» не нажата: {exc}"
        self._settle()
        if "выставлена на аукцион" in " ".join(self.body_text().split()).lower():
            return True, (
                f"выставлено: ставка {bid_gold} зол. {bid_silver} сер., "
                f"выкуп {buyout_gold} зол. {buyout_silver} сер."
            )
        return False, "лот не подтверждён игрой"

    def send_bag_item_to(self, recipient_id: str, item_id: str, message: str = "Снаряжение") -> bool:
        """Передать одну вещь из рюкзака почтой (вкладка «Вещи» -> «Рюкзак» -> выбрать)."""
        self.goto(f"https://barbars.ru/user/mail/send/id/{recipient_id}")
        if not self.click_href("sendMessageForm:mailItemLink"):
            return False
        self._settle()
        html = self.p.content()
        index: str | None = None
        for chunk in html.split("<div"):
            if f"item/id/{item_id}" in chunk:
                m = re.search(r"sendItemContainer:items:(\d+):selectLink", chunk)
                if m:
                    index = m.group(1)
                break
        if index is None:
            return False
        if not self.click_href(f"sendItemContainer:items:{index}:selectLink"):
            return False
        self._settle()
        try:
            self.p.fill("textarea[name='text']", message, timeout=5000)
        except Exception:
            pass
        try:
            self.p.click("input[type='submit'][value='отправить']", timeout=8000)
        except Exception:
            return False
        self._settle()
        return True

    def bag_items(self) -> list[dict[str, Any]]:
        """Содержимое рюкзака: [{index, item_id, name, mythic, personal, better,
        wear, crack}] — чтобы решать, что надеть, продать или разобрать."""
        self.goto("https://barbars.ru/user/rack")
        html = self.p.content()
        out: list[dict[str, Any]] = []
        for chunk, index in self._item_blocks(html):
            m = re.search(r"item/id/(\d+)\"><span>([^<]{2,60})</span>", chunk, re.S)
            text = " ".join(re.sub("<[^>]+>", " ", chunk).split())
            out.append(
                {
                    "index": index,
                    "item_id": m.group(1) if m else "",
                    "name": m.group(2).strip() if m else "",
                    "mythic": "bonusdarkiron" in chunk,
                    "personal": ", личный" in text,
                    "better": "Лучше" in text,
                    "wear": f"items:{index}:wearLink" in chunk,
                    "crack": "crackLink" in chunk,
                }
            )
        return out

    def hero_fatigue(self) -> int:
        """Усталость героя в процентах: 0 — нет, -30 — минус треть добычи.

        Страница героя `/user`: «усталость: -30%». По справке (/user/tire)
        усталость снижает клановый опыт, а также опыт и участие, получаемые
        в Башнях. Снимается за 5 золота (золото не тратим) или сама, если
        герой часов 9-10 не заходит в Башни.
        """
        from . import pages

        self.goto("https://barbars.ru/user")
        text = pages.cyr_normalize(self.body_text())
        m = re.search(r"усталость\s*:\s*(-?\d+)\s*%", text)
        return int(m.group(1)) if m else 0

    def battlefields_state(self) -> dict[str, Any]:
        """Состояние «Полей сражений» (/game/bg): когда следующий бой и счёт."""
        from . import pages

        self.goto("https://barbars.ru/game/bg")
        return pages.parse_battlefields(self.p.content(), self.body_text())

    def join_battlefields(self) -> bool:
        """Вступить в бой на Полях сражений (если бой идёт и есть кнопка)."""
        from . import pages

        state = pages.parse_battlefields(self.p.content(), self.body_text())
        links = state.get("join") or []
        if not links:
            return False
        link = links[0]
        href = str(link.get("href", ""))
        if href.startswith("?"):
            self.goto("https://barbars.ru/" + href)
        else:
            self.click_href(href) if "wicket:" in href else self.goto(href)
        self._settle()
        return True

    def join_current_fight(self, lair_url: str = "") -> bool:
        """Если идёт бой, в котором мы участвуем, — вернуться в него.

        Пока герой в бою, на странице пещер есть ссылка «Вернуться в бой»
        (`returnToGamePanel:currentGameLink`) — по ней открывается боевая панель.

        Для кланового босса работает и другой путь: во время попытки страница
        зала (`/game/dragonDungeon`) отдаёт боевую панель участнику — достаточно
        её перезагрузить. Поэтому зал проверяем последним, если указан.
        """
        if "Покинуть бой" in self.body_text():
            return True
        for url in ("https://barbars.ru/game/dungeons", "https://barbars.ru/"):
            self.goto(url)
            if "Вернуться в бой" not in self.body_text():
                continue
            if not self.click_text("Вернуться в бой"):
                continue
            self._settle()
            if "Покинуть бой" in self.body_text():
                return True
        if lair_url:
            self.goto(lair_url)
            text = self.body_text()
            if "Бить дракона" in text or "Лечить союзников" in text:
                return True
        return False

    def raid_room(self, url: str) -> dict[str, Any]:
        """Состояние зала кланового босса (/game/dragonDungeon и подобные)."""
        from . import pages

        self.goto(url)
        return pages.parse_raid_room(self.p.content(), self.body_text())

    def raid_ready(self) -> bool:
        """Отметить готовность к бою — «Я готов!».

        Кнопка переключается: после нажатия там «Я не готов!». Поэтому кликаем
        только если написано именно «Я готов!», иначе снимем свою готовность.
        """
        for link in self.p.locator("a").all():
            try:
                text = " ".join((link.inner_text() or "").split())
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if text != "Я готов!":
                continue
            if "readyLink" in href:
                try:
                    link.scroll_into_view_if_needed(timeout=3000)
                    link.click(timeout=8000)
                except Exception:
                    continue
            elif not self.click_href("readyPanel:readyLink"):
                continue
            self._settle()
            return True
        return False

    def raid_start(self) -> bool:
        """Начать бой с боссом — «Начать бой!» (зал закроется для остальных)."""
        if self.click_href("startCombatLink"):
            self._settle()
            return True
        return False

    def ability_options(self, ability_id: str) -> dict[str, Any]:
        """Варианты покупки умения за очки полей (вкладка «За очки полей»)."""
        from . import pages

        self.goto(f"https://barbars.ru/trade/ability/buy/0/{ability_id}")
        try:
            tab = self.p.locator("a:has-text('За очки полей')")
            if tab.count():
                tab.first.click(timeout=8000)
                self._settle()
        except Exception:
            pass
        return pages.parse_ability_options(self.p.content())

    def buy_ability_with_points(self, ability_id: str, index: int) -> bool:
        """Купить умение за очки полей (кнопка buyBlock:N:bgWinsBuyLink)."""
        self.goto(f"https://barbars.ru/trade/ability/buy/0/{ability_id}")
        try:
            tab = self.p.locator("a:has-text('За очки полей')")
            if tab.count():
                tab.first.click(timeout=8000)
                self._settle()
        except Exception:
            pass
        if not self.click_href(f"buyBlock:{index}:bgWinsBuyLink"):
            return False
        self._settle()
        self.confirm_if_needed()
        self._settle()
        return True

    def scroll_items(self) -> list[dict[str, str]]:
        """Свитки и книги в рюкзаке и сундуке.

        Основной список сундука уже содержит свитки (вкладка «Вещи»), вкладка
        «Свитки» нужна только как запасной вариант: иногда вместо списка
        открывается промо-страница акции.
        """
        out: list[dict[str, str]] = []
        seen: set[str] = set()

        def collect(html: str) -> int:
            found = 0
            for chunk in html.split('<div class="hr"></div>'):
                if "Свиток" not in chunk and "Манускрипт" not in chunk:
                    continue
                m = NAME_BLOCK_RE.search(chunk)
                if not m:
                    continue
                item_id, name = m.group(1), m.group(2).strip()
                if item_id in seen:
                    continue
                seen.add(item_id)
                out.append({"item_id": item_id, "name": name})
                found += 1
            return found

        for url in ("https://barbars.ru/user/rack", "https://barbars.ru/user/store"):
            self.goto(url)
            if collect(self.p.content()):
                continue
            for tab_name in ("Свитки", "Книги"):
                try:
                    tab = self.p.locator("a").filter(
                        has_text=re.compile(rf"^{re.escape(tab_name)}$")
                    )
                    if not tab.count():
                        continue
                    tab.first.click(timeout=8000)
                    self._settle()
                    collect(self.p.content())
                except Exception:
                    continue
        return out

    def activate_scroll(self, item_id: str, only_free: bool = True) -> tuple[bool, str]:
        """Активировать свиток (или прочитать книгу).

        Свиток активируется ссылками `scrollUse4Link` (на 4 часа) и
        `scrollUseAllLink` (на все 24 часа). При активном премиуме активация
        бесплатна (цена 0) — тогда активируем сразу. Обе опции проверяются по
        очереди: если одна платная, может быть бесплатная другая. Если цену не
        удалось прочитать, а рядом есть золото — не рискуем (золото не тратим).
        """
        self.goto(f"https://barbars.ru/item/id/{item_id}")
        html = self.p.content()
        notes: list[str] = []
        for marker, hours in (("scrollUseAllLink", "24 часа"), ("scrollUse4Link", "4 часа")):
            m = re.search(rf'href="([^"]*{marker}[^"]*)"', html)
            if not m:
                continue
            tail = html[m.end():m.end() + 500]
            price_m = re.search(r"цена[:\s]*(?:<[^>]+>\s*)*<span[^>]*>([\d\s]+)</span>", tail)
            if price_m:
                price = int(re.sub(r"\D", "", price_m.group(1)) or 0)
            elif "money_gold" in tail or "зол" in tail.lower():
                price = -1  # цена не распознана, но золото рядом есть — не рискуем
            else:
                price = 0
            if only_free and price != 0:
                reason = "цена не распознана" if price < 0 else f"цена {price} зол."
                notes.append(f"{hours}: {reason}")
                continue
            if self.click_href(marker):
                self._settle()
                self.confirm_if_needed()
                self._settle()
                return True, f"активирован на {hours}"
            notes.append(f"{hours}: не сработало")
        if notes:
            return False, "; ".join(notes) + " — не тратим золото"
        # книга: «прочитать книгу»
        if "bookOpenLink" in html:
            if self.click_href("bookOpenLink"):
                self._settle()
                self.confirm_if_needed()
                self._settle()
                return True, "книга прочитана"
        return False, "действие активации не найдено"

    def item_actions(self, item_id: str) -> list[str]:
        """Доступные действия со страницы вещи: «надеть», «на аукцион», …"""
        self.goto(f"https://barbars.ru/item/id/{item_id}")
        html = self.p.content()
        out = []
        for m in re.finditer(
            r'<a[^>]+href="([^"]*actionBlock[^"]*)"[^>]*>(.*?)</a>', html, re.S
        ):
            label = " ".join(re.sub("<[^>]+>", "", m.group(2)).split())
            if label:
                out.append(label)
        return out

    def buy_shop_item(self, href: str) -> bool:
        """Купить товар в магазине снаряжения (страница товара -> «Купить за …»)."""
        url = href if href.startswith("http") else f"https://barbars.ru/{href.lstrip('/')}"
        self.goto(url)
        if not self.click_href("border:buyoutLink"):
            return False
        # покупка может требовать подтверждения
        self.confirm_if_needed()
        return True

    def take_mail(self) -> bool:
        """Забрать всё из почты («ЗАБРАТЬ ВСЕ ИЗ ПОЧТЫ»)."""
        self.goto("https://barbars.ru/user/mail")
        return self.click_href("getAllFromMessages")

    def store_take_all(self, limit: int = 10) -> int:
        """Забрать всё со своей витрины (/user/public/store) в рюкзак."""
        taken = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/public/store")
            html = self.p.content()
            target = None
            for chunk, index in self._item_blocks(html):
                if f"items:{index}:toRackLink" in chunk:
                    target = index
                    break
            if target is None:
                break
            if not self.click_href(f"items:{target}:toRackLink"):
                break
            taken += 1
        return taken

    def send_store_items_to(self, recipient_id: str, message: str = "Снаряжение") -> bool:
        """Передать вещи с витрины другому игроку почтой.

        Форма: /user/mail/send/id/<id> -> вкладка «Вещи» -> источник «Витрина»
        -> «Выбрать все» -> кнопка «отправить».
        """
        self.goto(f"https://barbars.ru/user/mail/send/id/{recipient_id}")
        if not self.click_href("sendMessageForm:mailItemLink"):
            return False
        # источник — витрина (а не рюкзак)
        self.click_href("sendItemContainer:filterPublicStoreLink")
        if not self.click_href("sendItemContainer:selectAllLink"):
            return False
        try:
            self.p.fill("textarea[name='text']", message, timeout=5000)
        except Exception:
            pass
        try:
            self.p.click("input[type='submit'][value='отправить'], input[name=':submit']", timeout=5000)
        except Exception:
            return False
        self._settle()
        return True

    def send_resources_to(self, recipient_id: str, resource: str, amount: int) -> dict[str, Any]:
        """Передать другому игроку ресурс (железо/мифрил/бутылочки) почтой.

        Форма: /user/mail/send/id/<id> -> вкладка «Ресурсы» -> тип -> количество
        -> «отправить». Комиссия игры: 5 серебра за каждые 10 000 железа
        (или 5 мифрила / 10 бутылочек).
        """
        result: dict[str, Any] = {"ok": False, "message": ""}
        if amount <= 0:
            result["message"] = "нечего отправлять"
            return result
        type_value = {"iron": "2", "mifril": "3", "bottles": "1"}.get(resource)
        if type_value is None:
            result["message"] = f"неизвестный ресурс: {resource}"
            return result
        self.goto(f"https://barbars.ru/user/mail/send/id/{recipient_id}")
        if not self.click_href("sendMessageForm:mailGoodsLink"):
            result["message"] = "вкладка «Ресурсы» не открылась"
            return result
        try:
            self.p.select_option("select[name='type']", type_value, timeout=8000)
            self.p.fill("input[name='amount']", str(int(amount)), timeout=8000)
        except Exception as exc:  # noqa: BLE001
            result["message"] = f"не удалось заполнить форму: {str(exc).splitlines()[0]}"
            return result
        try:
            self.p.click("input[name=':submit'][value='отправить']", timeout=8000)
        except Exception:
            result["message"] = "кнопка «отправить» не нажалась"
            return result
        self._settle()
        text = " ".join(self.body_text().split())
        if "отправ" in text.lower() and "успеш" in text.lower():
            result["ok"] = True
        result["message"] = f"отправлено {amount} {resource}"
        return result

    def send_money_to(self, recipient_id: str, gold: int = 0, silver: int = 0) -> bool:
        """Передать золото/серебро другому игроку почтой.

        Форма: /user/mail/send/id/<id> -> вкладка «Деньги» -> суммы -> «отправить».
        Комиссия игры — 5% от суммы (но не менее 5).
        """
        if gold <= 0 and silver <= 0:
            return False
        self.goto(f"https://barbars.ru/user/mail/send/id/{recipient_id}")
        if not self.click_href("sendMessageForm:mailMoneyLink"):
            return False
        try:
            if gold > 0:
                self.p.fill("input[name='gold']", str(int(gold)), timeout=5000)
            if silver > 0:
                self.p.fill("input[name='silver']", str(int(silver)), timeout=5000)
        except Exception:
            return False
        try:
            self.p.click("input[name=':submit'][value='отправить']", timeout=5000)
        except Exception:
            return False
        self._settle()
        return True

    def sell_duplicate_items(self, limit: int = 3) -> int:
        """Выставить на витрину лишние мифические вещи (дубли по слотам).

        Дубль — вещь, чей слот уже занят надетой вещью. Такие вещи не нужны
        герою, но их нельзя разобрать (мифические), поэтому продаём.
        """
        from . import pages

        worn = self.worn_gear()
        busy = {w.get("slot", "") for w in worn if w.get("slot")}
        sold = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/rack")
            html = self.p.content()
            target: str | None = None
            for chunk, index in self._item_blocks(html):
                if "bonusdarkiron" not in chunk:
                    continue
                if "Лучше" in chunk:
                    continue  # лучше надетого — сначала надеваем
                name = re.search(r"item/id/\d+\"><span>([^<]+)</span>", chunk)
                item_id = re.search(r"item/id/(\d+)", chunk)
                if not name or not item_id:
                    continue
                slot, _kind = pages.slot_of(name.group(1))
                if not slot or slot not in busy:
                    continue
                target = item_id.group(1)
                break
            if not target:
                break
            if not self.sell_item_to_store(target):
                break
            sold += 1
        return sold

    def mail_pending(self) -> bool:
        """Есть ли на почте что забирать (письма с вещами или деньгами).

        Важно: кнопка «ЗАБРАТЬ ВСЕ ИЗ ПОЧТЫ» есть на странице всегда, её
        наличие не значит, что есть письма. Смотрим именно на пометку
        «ЗАБРАТЬ» в самих письмах.
        """
        self.goto("https://barbars.ru/user/mail")
        html = self.p.content()
        if "getAllFromMessages" not in html:
            return False
        text = re.sub(r"<[^>]+>", " ", html)
        text = " ".join(text.split())
        # «ЗАБРАТЬ» в письме, но не кнопка «ЗАБРАТЬ ВСЕ ИЗ ПОЧТЫ»
        if re.search(r"ЗАБРАТЬ(?!\s+ВСЕ)", text):
            return True
        return "пришли" in text.lower()

    # ------------------------------------------------------------------ торговля

    def open_bazaar_tab(self, resource: str = "bottles") -> bool:
        """Открыть аукцион ресурсов на нужной вкладке (bottles/mifril/iron)."""
        self.goto("https://barbars.ru/trade/bazaar")
        pattern = {
            "bottles": "filterPotionsLink",
            "mifril": "filterMifrilLink",
            "iron": "filterIronLink",
            "mine": "filterMyLotsLink",
        }.get(resource, "filterPotionsLink")
        return self.click_href(pattern)

    def iron_lots(self) -> list[dict[str, Any]]:
        """Лоты железа на аукционе ресурсов: количество, цена в золоте и серебре."""
        from . import pages

        if not self.open_bazaar_tab("iron"):
            return []
        out: list[dict[str, Any]] = []
        pattern = re.compile(
            r"<img[^>]*ironbar[^>]*>\s*<span>(\d+)</span>\s*<span>жлз</span>\s*<span>(.*?)</span>\s*"
            r'<a[^>]*href="([^"]*buyLink[^"]*)"',
            re.S,
        )
        for m in pattern.finditer(self.p.content() or ""):
            price_html = m.group(2)
            gold = re.search(r"money_gold[^>]*>\s*<span>(\d+)</span>", price_html)
            silver = re.search(r"money_silver[^>]*>\s*<span>(\d+)</span>", price_html)
            out.append(
                {
                    "qty": int(m.group(1)),
                    "gold": int(gold.group(1)) if gold else 0,
                    "silver": int(silver.group(1)) if silver else 0,
                    "href": m.group(3),
                }
            )
        return out

    def buy_iron_with_gold(self, min_iron: int, max_gold: int) -> dict[str, Any]:
        """Купить железо на аукционе ресурсов, потратив не больше max_gold золота.

        Лоты железа выставлены в золоте и серебре (например, 2 000 000 железа
        = 40 зол). Покупаем самый дешёвый по «золото на 1000 железа», если он
        укладывается в лимит золота, и только если железа реально не хватает.
        """
        result: dict[str, Any] = {"ok": False, "message": "", "qty": 0, "gold": 0}
        lots = self.iron_lots()
        if not lots:
            result["message"] = "лоты железа не найдены"
            return result

        def score(lot: dict[str, Any]) -> float:
            return (lot["gold"] * 1000 + lot["silver"] * 20) / max(1, lot["qty"])

        affordable = [lot for lot in lots if lot["gold"] <= max_gold and lot["qty"] >= min_iron]
        if not affordable:
            result["message"] = (
                f"нет лотов железа под лимит {max_gold} зол "
                f"(минимум {min_iron} железа); доступно {len(lots)} лотов"
            )
            return result
        best = min(affordable, key=score)
        url = best["href"]
        if not url.startswith("http"):
            url = f"https://barbars.ru/{url.lstrip('./').lstrip('/')}"
        self.goto(url)
        # страница подтверждения: «Подтверди, что ты хочешь купить: N жлз по цене G»
        text = " ".join(self.body_text().split())
        if "Да, подтверждаю" not in text:
            result["message"] = "страница подтверждения не открылась"
            return result
        if not self.click_text("Да, подтверждаю"):
            result["message"] = "не удалось подтвердить покупку"
            return result
        self._settle()
        result["ok"] = True
        result["qty"] = best["qty"]
        result["gold"] = best["gold"]
        result["message"] = (
            f"куплено {best['qty']} железа за {best['gold']} зол + {best['silver']} сер"
        )
        return result

    def sell_resource(
        self,
        resource: str,
        amount: int,
        gold: int = 0,
        silver: int = 0,
    ) -> dict[str, Any]:
        """Выставить ресурс на аукционе.

        Страница: /trade/bazaar -> «Выставить ресурсы» -> форма
        (тип товара, количество, цена в золоте и серебре).
        """
        result: dict[str, Any] = {"ok": False, "message": ""}
        type_value = {"bottles": "1", "iron": "2", "mifril": "3"}.get(resource)
        if type_value is None:
            result["message"] = f"неизвестный ресурс: {resource}"
            return result
        if amount <= 0:
            result["message"] = "нечего продавать"
            return result

        self.goto("https://barbars.ru/trade/bazaar")
        if not self.click_text("Выставить ресурсы"):
            result["message"] = "форма выставления не открылась"
            return result
        before = self._resource_amount(resource)
        try:
            self.p.select_option("select[name='type']", type_value, timeout=8000)
            self.p.fill("input[name='amount']", str(amount), timeout=8000)
            self.p.fill("input[name='costGold']", str(int(gold)), timeout=8000)
            self.p.fill("input[name='costSilver']", str(int(silver)), timeout=8000)
            self.human.pause("action")
            self.p.click("input[type='submit'][value='выставить']", timeout=8000)
        except Exception as exc:
            result["message"] = f"ошибка формы: {str(exc).splitlines()[0]}"
            return result
        self._settle()
        self.human.pause("page")
        text = self.body_text()
        after = self._resource_amount(resource)
        result["message"] = f"лот выставлен: {amount} {resource} за {gold}з {silver}с"
        if before is not None and after is not None and before - after == amount:
            result["ok"] = True
            return result
        if re.search(r"(отменить|мои лоты)", text, re.IGNORECASE):
            result["ok"] = True
            result["message"] += " (лот виден в «Мои лоты»)"
            return result
        if re.search(r"(уже есть активный лот|нельзя|ошибк|недостаточно|неверн)", text, re.IGNORECASE):
            result["ok"] = False
            result["message"] = "лот не выставлен: " + " ".join(text.split()[-12:])[:200]
            return result
        result["ok"] = False
        result["message"] = "результат выставления неясен"
        return result

    def _resource_amount(self, resource: str) -> int | None:
        """Текущее количество ресурса в инвентаре (по вкладке ресурсов)."""
        st = self.status()
        return {"bottles": st.bottles, "mifril": st.mifril, "iron": st.iron}.get(resource)

    def my_lots(self, resource: str) -> list[dict[str, Any]]:
        """Мои активные лоты по ресурсу (вкладка «Мои лоты»)."""
        self.goto("https://barbars.ru/trade/bazaar")
        self.click_href("filterMyLotsLink")
        from . import pages

        return pages.parse_lots(self.p.content(), resource)

    def cancel_lot(self, resource: str = "bottles") -> bool:
        """Снять свой лот («[отменить]» во вкладке «Мои лоты»)."""
        self.goto("https://barbars.ru/trade/bazaar")
        self.click_href("filterMyLotsLink")
        html = self.p.content()
        # ищем блок лота нужного ресурса и ссылку «отменить» рядом
        for match in re.finditer(
            r"<div>(?:(?!</div>).)*?/images/icons/(?P<res>bottle|mifrilbar|ironbar)\.png"
            r"(?:(?!</div>).)*?</div>",
            html,
            re.S,
        ):
            block = match.group(0)
            icons = {"bottle": "bottles", "mifrilbar": "mifril", "ironbar": "iron"}
            if icons.get(match.group("res")) != resource:
                continue
            if "отменить" not in block.lower():
                continue
            for link in self.p.locator("a").all():
                try:
                    label = (link.inner_text() or "").strip().lower()
                    href = link.get_attribute("href") or ""
                except Exception:
                    continue
                if "отменить" in label or "cancel" in href.lower():
                    try:
                        link.click(timeout=8000)
                    except Exception:
                        continue
                    self._settle()
                    self.human.pause("action")
                    return True
        return False

    def well_daily_gift(self) -> bool:
        """Ежедневный бесплатный подарок колодца удачи."""
        self.goto("https://barbars.ru/trade/well")
        return self.click_href("getDailyGiftLink")

    def well_ancient_book(self) -> bool:
        """Древняя книга: 10000 железа -> 5 бутылочек (раз в день)."""
        self.goto("https://barbars.ru/trade/well")
        return self.click_href("getBookLink")

    def buy_exp_with_iron(self, iron_amount: int) -> dict[str, Any]:
        """Купить опыт у мудреца за железо (не за золото).

        На /trade/ironmaster варианты: «Пожертвовать 10000 железа» (5% опыта),
        «Пожертвовать 5000 железа» (2% опыта).
        """
        result: dict[str, Any] = {"ok": False, "message": ""}
        self.goto("https://barbars.ru/trade/ironmaster")
        for link in self.p.locator("a").all():
            try:
                label = (link.inner_text() or "").strip().replace("\n", " ")
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if "Пожертвовать" not in label or "желез" not in label.lower():
                continue
            m = re.search(r"Пожертвовать\s*([\d\s]+)\s*железа", label, re.IGNORECASE)
            if not m:
                continue
            cost = parse_amount(m.group(1))
            if cost != iron_amount:
                continue
            try:
                self.human.move_mouse_to(self.p, link)
                self.human.pause("action")
                link.click(timeout=8000)
            except Exception as exc:
                result["message"] = f"клик не удался: {str(exc).splitlines()[0]}"
                return result
            self._settle()
            self.human.pause("page")
            result = {"ok": True, "message": f"опыт куплен за {cost} железа", "cost": cost}
            return result
        result["message"] = f"варианта «{iron_amount} железа» нет"
        return result

    def buy_exp_with_gold(self, gold_amount: int) -> dict[str, Any]:
        """Купить опыт у мудреца за золото.

        В мобильной сборке игры мудрец отдаёт опыт только за золото:
        «Пожертвовать 7 золота» (14% опыта), «Пожертвовать 5 золота» (10%).
        Железо в этой сборке купить нельзя — рынка ресурсов нет, поэтому
        золото — единственный способ докупить прогресс.
        """
        result: dict[str, Any] = {"ok": False, "message": ""}
        self.goto("https://barbars.ru/trade/ironmaster")
        for link in self.p.locator("a").all():
            try:
                label = (link.inner_text() or "").strip().replace("\n", " ")
            except Exception:
                continue
            if "Пожертвовать" not in label or "золот" not in label.lower():
                continue
            m = re.search(r"Пожертвовать\s*([\d\s]+)\s*золота", label, re.IGNORECASE)
            if not m:
                continue
            cost = parse_amount(m.group(1))
            if cost != gold_amount:
                continue
            try:
                self.human.move_mouse_to(self.p, link)
                self.human.pause("action")
                link.click(timeout=8000)
            except Exception as exc:
                result["message"] = f"клик не удался: {str(exc).splitlines()[0]}"
                return result
            self._settle()
            self.human.pause("page")
            return {"ok": True, "message": f"опыт куплен за {cost} золота", "cost": cost}
        result["message"] = f"варианта «{gold_amount} золота» нет"
        return result

    # ------------------------------------------------------------------ рюкзак и вещи

    @staticmethod
    def _item_blocks(html: str) -> list[tuple[str, str]]:
        """Разбить страницу рюкзака/сундука на блоки предметов: (html блока, href индекса)."""
        blocks: list[tuple[str, str]] = []
        for chunk in html.split('<div class="hr"></div>'):
            m = re.search(r'href="([^"]*items:(\d+):[^"]*)"', chunk)
            if m:
                blocks.append((chunk, m.group(2)))
        return blocks

    def bag_item_ids(self) -> list[str]:
        """id всех вещей, которые сейчас лежат в рюкзаке."""
        self.goto("https://barbars.ru/user/rack")
        html = self.p.content()
        return list(dict.fromkeys(re.findall(r"item/id/(\d+)", html)))

    def bag_counts(self) -> dict[str, int]:
        """Сколько мест в рюкзаке и сундуке, и сколько занято."""
        self.goto("https://barbars.ru/user/rack")
        text = self.body_text()
        out = {"bag_used": 0, "bag_total": 0, "chest_used": 0, "chest_total": 0}
        m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", text)
        if m:
            out["bag_used"], out["bag_total"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"Открыть сундук\s*\((\d+)\s*/\s*(\d+)\)", text)
        if m:
            out["chest_used"], out["chest_total"] = int(m.group(1)), int(m.group(2))
        return out

    def confirm_if_needed(self) -> bool:
        """Подтвердить действие, если игра требует подтверждения.

        Например, надеть вещь: «Вещь станет личной… Подтверди, что хочешь
        надеть эту вещь» → «Да, подтверждаю». Без этого вещь не надевается.
        """
        try:
            return self.click_text("Да, подтверждаю")
        except Exception:
            return False

    def equip_better_items(self, limit: int = 8) -> int:
        """Надеть вещи, помеченные «Лучше (+N)» — герой становится сильнее.

        Также подтягиваем «Лучше» из сундука: там тоже лежат вещи сильнее надетых.
        """
        worn = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/rack")
            html = self.p.content()
            target = None
            for chunk, index in self._item_blocks(html):
                if "Лучше" in chunk and f"items:{index}:wearLink" in chunk:
                    target = index
                    break
            if target is None:
                # ищем «Лучше» в сундуке и переносим в рюкзак
                self.goto("https://barbars.ru/user/store")
                store_html = self.p.content()
                store_target = None
                for chunk, index in self._item_blocks(store_html):
                    if "Лучше" in chunk and f"items:{index}:toRackLink" in chunk:
                        store_target = index
                        break
                if store_target is None:
                    break
                if not self.click_href(f"items:{store_target}:toRackLink"):
                    break
                continue
            if not self.click_href(f"items:{target}:wearLink"):
                break
            # игра спрашивает подтверждение («вещь станет личной»)
            self.confirm_if_needed()
            worn += 1
        return worn

    @staticmethod
    def _is_scroll_or_book(chunk: str) -> bool:
        """Свитки и книги не ломаем — их активируем (бесплатно) и читаем."""
        return (
            "Свиток" in chunk
            or "Манускрипт" in chunk
            or "scrollUse" in chunk
            or "bookOpen" in chunk
        )

    def crack_items(
        self,
        limit: int = 20,
        keep_better: bool = True,
        keep_mythic: bool = True,
    ) -> int:
        """Разобрать вещи в рюкзаке на железо.

        Правило игрока: ломаем всё, что не надето и не нужно, кроме мифических
        вещей (иконка `bonusdarkiron`) — их не ломаем. Пометка «Лучше» означает
        «сильнее надетого» — такую вещь сначала надевают, и ломать её нельзя.
        Свитки и книги не ломаем никогда.

        Ссылка разбора `items:N:crackIronPanel:crackLink` есть в списке рюкзака
        не у всех вещей (у эпических и мифических её нет) — для них разбор
        делается со страницы вещи (`actionBlock:crackIronPanel:crackLink`).
        """
        cracked = 0
        tried: set[str] = set()
        for _ in range(max(1, limit)):
            self.goto("https://barbars.ru/user/rack")
            html = self.p.content()
            target: tuple[str, str] | None = None
            for chunk, index in self._item_blocks(html):
                if keep_better and "Лучше" in chunk:
                    continue
                if keep_mythic and "bonusdarkiron" in chunk:
                    continue  # мифические вещи не ломаем
                if self._is_scroll_or_book(chunk):
                    continue  # свитки и книги не разбираем
                if f"list:{index}" in tried:
                    continue
                if f"items:{index}:crackIronPanel:crackLink" in chunk:
                    target = ("list", str(index))
                    break
                item_id = re.search(r'href="(?:\.\./)*item/id/(\d+)"', chunk)
                if item_id and item_id.group(1) not in tried:
                    target = ("page", item_id.group(1))
                    break
            if target is None:
                break
            if target[0] == "list":
                ok = self.click_href(f"items:{target[1]}:crackIronPanel:crackLink")
                key = f"list:{target[1]}"
            else:
                ok = self._crack_item_page(target[1])
                key = target[1]
            if not ok:
                # вещь не разбирается (например, «личная») — не застреваем,
                # пробуем следующую, иначе чистка рюкзака встаёт целиком
                tried.add(key)
                continue
            cracked += 1
        return cracked

    def sell_item_to_store(self, item_id: str) -> bool:
        """Выставить вещь на «Витрину клана» (/guild/public/store).

        Со страницы вещи ссылка `actionBlock:toPublicStoreLink` сразу отправляет
        вещь на витрину клана (без формы). Это единственный способ продать
        снаряжение: обычный аукцион — только для ресурсов.
        """
        self.goto(f"https://barbars.ru/item/id/{item_id}")
        return self.click_href("toPublicStoreLink")

    def sell_extra_items(self, limit: int = 3) -> int:
        """Выставить ненужные вещи на витрину клана.

        Берём мифические вещи (их нельзя разобрать на железо), которые не
        помечаются как «Лучше» и которые нельзя надеть (нет ссылки «надеть»):
        они только занимают рюкзак. Такие вещи идут на витрину — так они
        продаются за серебро/золото, а не просто исчезают.
        """
        sold = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/rack")
            html = self.p.content()
            target: str | None = None
            for chunk, index in self._item_blocks(html):
                if "bonusdarkiron" not in chunk:
                    continue
                if "Лучше" in chunk:
                    continue
                if f"items:{index}:wearLink" in chunk:
                    continue  # можно надеть — сначала надеваем, не продаём
                item_id = re.search(r'href="(?:\.\./)*item/id/(\d+)"', chunk)
                if item_id:
                    target = item_id.group(1)
                    break
            if target is None:
                break
            if not self.sell_item_to_store(target):
                break
            sold += 1
        return sold

    def _crack_item_page(self, item_id: str) -> bool:
        """Разобрать вещь со страницы самой вещи (`/item/id/<id>`)."""
        self.goto(f"https://barbars.ru/item/id/{item_id}")
        html = self.p.content()
        if "crackIronPanel:crackLink" not in html:
            return False
        return self.click_href("crackIronPanel:crackLink")

    def crack_chest_items(
        self,
        limit: int = 20,
        keep_mythic: bool = True,
        keep_better: bool = True,
    ) -> int:
        """Разобрать вещи в сундуке на железо.

        В списке сундука разбора нет (только «в рюкзак»), поэтому ломаем со
        страницы вещи — ссылка `actionBlock:crackIronPanel:crackLink` там есть
        и работает (проверено: эпическая вещь из сундука разобралась).

        Мифические вещи (`bonusdarkiron`) не ломаем; «Лучше» сначала надеваем.
        Свитки и книги не ломаем — их активируем и читаем. Если вещь не
        разбирается, пробуем следующую (иначе чистка сундука встаёт целиком).
        """
        cracked = 0
        tried: set[str] = set()
        for _ in range(max(1, limit)):
            self.goto("https://barbars.ru/user/store")
            html = self.p.content()
            target: str | None = None
            for chunk, index in self._item_blocks(html):
                if keep_better and "Лучше" in chunk:
                    continue
                if keep_mythic and "bonusdarkiron" in chunk:
                    continue
                if self._is_scroll_or_book(chunk):
                    continue  # свитки и книги не разбираем
                item_id = re.search(r'href="(?:\.\./)*item/id/(\d+)"', chunk)
                if item_id and item_id.group(1) not in tried:
                    target = item_id.group(1)
                    break
            if target is None:
                break
            tried.add(target)
            if not self._crack_item_page(target):
                continue  # не разобралась — пробуем следующую
            cracked += 1
        return cracked

    def crack_all_items(self) -> bool:
        """«Разобрать всё на железо» — аварийный вариант для полного рюкзака."""
        self.goto("https://barbars.ru/user/rack")
        return self.click_href("crackAllIronLink")

    def master_state(self) -> dict[str, Any]:
        """Одна загрузка /user/master: варианты параметров и цена мастерства.

        {"params": [{"param": "strength", "cost": 10000, "gain": 8,
        "currency": "iron", "href": ...}], "mastery": {"iron": 35000, "mifril": 200}}
        """
        self.goto("https://barbars.ru/user/master")
        return parse_master_page(self.p.content())

    def master_upgrade_options(self) -> list[dict[str, Any]]:
        """Параметры героя, которые можно улучшить: /user/master.

        Возвращает список: {"param": "strength", "cost": 10000, "currency": "iron"}.
        Улучшение параметров у разных героев стоит то золота, то железа —
        золото по правилам не тратим, поэтому его пропускаем.
        """
        return self.master_state()["params"]

    def upgrade_master_param(self, href: str) -> bool:
        """Нажать «улучшить» у конкретного параметра на /user/master."""
        self.goto("https://barbars.ru/user/master")
        return self.click_href(href)

    def mastery_level_cost(self) -> dict[str, int]:
        """Стоимость повышения уровня мастерства: {"iron": ..., "mifril": ...}."""
        return self.master_state()["mastery"]

    def upgrade_mastery_level(self) -> bool:
        """Повысить уровень мастерства (кнопка «Повысить за …»)."""
        self.goto("https://barbars.ru/user/master")
        return self.click_href("upgradeLink")

    def stash_items(self, keep: int = 4, limit: int = 20) -> int:
        """Сложить лишние вещи в сундук, чтобы освободить рюкзак.

        Сначала убираем вещи без пометки «Лучше» (они хуже надетых).
        """
        moved = 0
        for _ in range(limit):
            self.goto("https://barbars.ru/user/rack")
            text = self.body_text()
            m = re.search(r"Рюкзак\s*\((\d+)\s*/\s*(\d+)\)", text)
            used = int(m.group(1)) if m else 0
            if used <= keep:
                break
            m = re.search(r"Открыть сундук\s*\((\d+)\s*/\s*(\d+)\)", text)
            if m and int(m.group(1)) >= int(m.group(2)):
                break  # сундук полон
            html = self.p.content()
            target = None
            for chunk, index in self._item_blocks(html):
                if f"items:{index}:toStoreLink" in chunk and "Лучше" not in chunk:
                    target = index
                    break
            if target is None:
                for chunk, index in self._item_blocks(html):
                    if f"items:{index}:toStoreLink" in chunk:
                        target = index
                        break
            if target is None:
                break
            if not self.click_href(f"items:{target}:toStoreLink"):
                break
            moved += 1
        return moved

    def autocrack_active(self) -> str | None:
        """Какой режим авторазбора включён сейчас.

        На странице активный пункт выводится текстом без ссылки, остальные —
        ссылками. Поэтому «нет ссылки» + «текст есть» = этот режим включён.
        """
        labels = (
            ("autoCrackOffLink", "Не разбирать вещи"),
            ("autoCrackCommonLink", "обычные вещи"),
            ("autoCrackUncommonLink", "необычные вещи и хуже"),
            ("autoCrackRareLink", "редкие вещи и хуже"),
            ("autoCrackEpicLink", "эпические вещи и хуже"),
            ("autoCrackLegendaryLink", "легендарные вещи и хуже"),
        )
        text = self.body_text().lower()
        for href, label in labels:
            if self.p.locator(f"a[href*='{href}']").count() > 0:
                continue
            if label.lower() in text:
                return href
        return None

    def set_autocrack(self, kind: str) -> bool:
        """Включить авторазбор: kind = autoCrackCommonLink | autoCrackUncommonLink | ...

        Режим «обычные вещи» (autoCrackCommonLink) на странице не является
        ссылкой — он уже включён по умолчанию, поэтому кликать нечего.
        """
        self.goto("https://barbars.ru/user/rack/autocrack")
        if self.click_href(kind):
            return True
        return self.autocrack_active() == kind

    # ------------------------------------------------------------------ активности

    def has_combat_button(self) -> bool:
        """Есть ли на странице кнопка атаки (значит можно биться)."""
        for link in self.p.locator("a").all():
            try:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip()
            except Exception:
                continue
            if "damageLastTargetLink" in href or "damageOgreLink" in href:
                return True
            if text.startswith(("Бить", "Атаковать", "Жечь", "Ударить", "Атака")):
                return True
        return False

    def _combat_costs_gold(self) -> bool:
        """Кнопка боя рядом с ценой в золоте — такой бой платный."""
        for link in self.p.locator("a").all():
            try:
                text = (link.inner_text() or "").strip()
            except Exception:
                continue
            if text.startswith(("Бить", "Атаковать", "Ударить", "Жечь")) and self._near_gold(link):
                return True
        return False

    def enter_activity(self, url: str, wait_sec: int = 90) -> dict[str, Any]:
        """Зайти в активность и дождаться боя.

        Активности разные: у одних сразу есть противник («Бить ...»),
        у других нужно нажать «Войти в замок» / «Начать бой!» / «Встать в очередь»
        и дождаться, пока противник появится (арена, выживание, клановые боссы).

        У клановых боссов вход двухшаговый: «Начать бой!» → панель готовности
        «Я готов!» → и только после этого начинается бой.
        """
        result: dict[str, Any] = {"ok": False, "stage": "", "note": ""}
        self.goto(url)
        if self.has_combat_button():
            if self._combat_costs_gold():
                result["note"] = "бой платный (золото) — не тратим"
                return result
            result.update(ok=True, stage="fight")
            return result

        entered = False
        # арена и выживание: если мы уже в очереди («Очередь: 1 из 8»), бой
        # начнётся сам — ждём, ничего не нажимая (кнопка «Новый бой» сбросила бы
        # очередь, и мы бы потеряли место)
        text = self.body_text()
        if "Очередь:" in text:
            result["stage"] = "очередь"
            deadline = time.time() + max(10, wait_sec)
            while time.time() < deadline:
                if self.has_combat_button():
                    result.update(ok=True, stage="fight")
                    return result
                self.reload()
                time.sleep(6)
            result["note"] = "бой не начался за отведённое время"
            return result

        for label in ("Начать бой!", "Новый бой", "Войти в замок", "Войти", "Встать в очередь"):
            # вход может быть платным (золото или серебро) — по правилам игрока
            # за вход не платим, поэтому такие кнопки пропускаем
            if self._click_any_text(label, avoid_gold=True, avoid_paid=True):
                entered = True
                result["stage"] = label
                break
        if not entered:
            text = self.body_text()
            note = ""
            m = re.search(r"(Начать бой может[^\n.]*|нужно[^\n.]*участи[^\n.]*)", text, re.IGNORECASE)
            if m:
                note = m.group(1)
            result["note"] = note or "нет кнопки входа"
            return result

        deadline = time.time() + max(10, wait_sec)
        ready_clicked = False
        while time.time() < deadline:
            if self.has_combat_button():
                result.update(ok=True, stage="fight")
                return result
            # панель готовности (клановые боссы): нужно подтвердить «Я готов!»
            if not ready_clicked and self.click_href("readyLink"):
                ready_clicked = True
                result["stage"] = "Я готов!"
                continue
            self.reload()
            time.sleep(6)
        result["note"] = "бой не начался за отведённое время"
        return result

    def _near_gold(self, locator: Any) -> bool:
        """Рядом с кнопкой упоминается золото — значит, действие платное.

        Проверяем и саму кнопку («Бить дракона за 4 золота»), и её блок —
        иначе платный бой можно было бы случайно начать.
        """
        return self._near_paid(locator, ("money_gold", "зол"))

    def _near_paid(self, locator: Any, marks: tuple[str, ...] = ("money_gold", "money_silver", "зол", "сер")) -> bool:
        """Рядом с кнопкой — цена в золоте или серебре: действие платное.

        Смотрим саму кнопку и только компактный блок вокруг неё (tr/li/span):
        если взять большой родительский div, то рядом всегда найдётся счётчик
        в шапке страницы и все входы будут считаться платными.
        """
        try:
            info = locator.evaluate(
                """el => {
                    const compact = el.closest('tr') || el.closest('li')
                        || (el.parentElement
                            && ['SPAN', 'BUTTON', 'A', 'TD'].includes(el.parentElement.tagName)
                            ? el.parentElement : null);
                    const imgs = Array.from(compact ? compact.querySelectorAll('img') : [])
                        .map(i => i.getAttribute('src') || '').join(' ');
                    const own = Array.from(el.querySelectorAll('img'))
                        .map(i => i.getAttribute('src') || '').join(' ');
                    return (el.innerText || '') + ' ' +
                           (compact ? (compact.innerText || '') : '') + ' ' + imgs + ' ' + own;
                }"""
            )
        except Exception:
            return False
        text = str(info or "").lower()
        return any(mark.lower() in text for mark in marks)

    def _click_any_text(self, label: str, avoid_gold: bool = False, avoid_paid: bool = False) -> bool:
        """Кликнуть по элементу с текстом — не только <a>, но и span/div/button.

        В игре кнопки входа («Встать в очередь», «Войти в замок») — обычные
        <span>/<div> с обработчиком, а не ссылки. При `avoid_gold` платные
        кнопки (рядом золото) пропускаются — золото тратить нельзя;
        `avoid_paid` — то же для серебра.
        """
        for tag in ("a", "button", "span", "div", "li", "input"):
            try:
                locator = self.p.locator(f"{tag}:has-text('{label}')")
                count = locator.count()
            except Exception:
                continue
            for index in range(min(count, 6)):
                target = locator.nth(index)
                try:
                    text = (target.inner_text() or "").strip()
                except Exception:
                    continue
                if label not in text or len(text) > len(label) + 40:
                    continue
                if avoid_paid and self._near_paid(target):
                    continue
                if avoid_gold and self._near_gold(target):
                    continue
                try:
                    target.scroll_into_view_if_needed(timeout=3000)
                    self.human.move_mouse_to(self.p, target)
                    self.human.pause("action")
                    target.click(timeout=8000)
                except Exception:
                    continue
                self._settle()
                self.human.pause("action")
                return True
        return False

    def dump_page(self, name: str, out_dir: str | Path) -> Path:
        """Сохранить HTML+текст страницы — для разбора новых экранов."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        html_path = out / f"{name}.html"
        html_path.write_text(self.p.content(), encoding="utf-8")
        txt_path = out / f"{name}.txt"
        txt_path.write_text(self.body_text(), encoding="utf-8")
        return html_path
