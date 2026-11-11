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
        try:
            if self._context:
                self._context.close()
        finally:
            if self._playwright:
                self._playwright.stop()
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
                lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
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
        """Жив ли ещё браузер (окно могли закрыть)."""
        try:
            return self.page is not None and not self.page.is_closed()
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
        st.gold = self._icon_value(["money_gold.png"])
        st.silver = self._icon_value(["money_silver.png"])
        st.iron = self._icon_value(["ironbar.png"])
        st.mifril = self._icon_value(["mifrilbar.png"])
        st.bottles = self._icon_value(["bottle.png"])
        return st

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
            hero_id = re.search(r"(\d+)$", body_link.get_attribute("href") or "")
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
            except Exception:
                continue
            if not text:
                continue
            if text.startswith("Бить"):
                flat = text.split("\n")[0].strip()
                cs.attack_links.append(flat)
                cs.enemy_name = flat[len("Бить") :].strip()
            elif text.startswith("Лечить"):
                cs.heal_links.append(text.split("\n")[0].strip())
            elif text.startswith("Сбежать") or text.startswith("Отступить") or text.startswith("Убежать"):
                cs.flee_links.append(text.split("\n")[0].strip())
            elif "бутылочк" in text.lower() or "зелье" in text.lower() or "выпить" in text.lower():
                cs.potion_links.append(text.split("\n")[0].strip())

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
        """Сколько боёв осталось: {'dungeon': n, 'duel': m}."""
        limits: dict[str, int] = {}
        text = self.body_text()
        m = re.search(r"провести\s*(\d+)\s*бо(?:я|и|ев)\s*в подземельях\s*и\s*(\d+)\s*бо(?:я|и|ев)\s*в дуэлях", text, re.IGNORECASE)
        if m:
            limits["dungeon"] = int(m.group(1))
            limits["duel"] = int(m.group(2))
        for name, count in re.findall(r"([^\n]*?)\s+осталось\s*(\d+)\s*бо", text):
            key = name.strip().lower()
            if "дуэл" in key:
                limits["duel"] = int(count)
            elif "башн" in key or "подзем" in key or "пещер" in key:
                limits["dungeon"] = int(count)
            else:
                limits.setdefault(key, int(count))
        return limits

    # ------------------------------------------------------------------ actions

    def repair_all(self) -> bool:
        """'Починить все вещи за N' — починка всего снаряжения железом."""
        locator = self.p.locator("a:has-text('Починить все'), button:has-text('Починить все')")
        if locator.count() == 0:
            return False
        try:
            locator.first.click(timeout=8000)
        except Exception:
            return False
        self._settle()
        return True

    def take_clan_quest(self, index: int = 0) -> bool:
        locator = self.p.locator("a:has-text('Взять задание'), button:has-text('Взять задание')")
        if locator.count() == 0:
            return False
        try:
            locator.nth(min(index, locator.count() - 1)).click(timeout=8000)
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
            if text.startswith(("Бить", "Атаковать", "Жечь")):
                return True
        return False

    def enter_activity(self, url: str, wait_sec: int = 90) -> dict[str, Any]:
        """Зайти в активность и дождаться боя.

        Активности разные: у одних сразу есть противник («Бить ...»),
        у других нужно нажать «Войти в замок» / «Начать бой!» / «Встать в очередь»
        и дождаться, пока противник появится (арена, выживание, клановые боссы).
        """
        result: dict[str, Any] = {"ok": False, "stage": "", "note": ""}
        self.goto(url)
        if self.has_combat_button():
            result.update(ok=True, stage="fight")
            return result

        entered = False
        for label in ("Начать бой!", "Войти в замок", "Войти", "Встать в очередь"):
            if self._click_any_text(label):
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
        while time.time() < deadline:
            if self.has_combat_button():
                result.update(ok=True, stage="fight")
                return result
            self.reload()
            time.sleep(6)
        result["note"] = "бой не начался за отведённое время"
        return result

    def _click_any_text(self, label: str) -> bool:
        """Кликнуть по элементу с текстом — не только <a>, но и span/div/button.

        В игре кнопки входа («Встать в очередь», «Войти в замок») — обычные
        <span>/<div> с обработчиком, а не ссылки.
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
