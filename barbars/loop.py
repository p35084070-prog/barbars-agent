"""Основной цикл агента: сбор состояния -> решение -> действие -> повтор."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from . import pages, rules
from .driver import Game
from .llm import ClaudeAdvisor


class Agent:
    def __init__(self, game: Game, config: dict[str, Any], log_dir: str | Path = "logs"):
        self.game = game
        self.config = config
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # имя аккаунта: чтобы логи и дневные счётчики разных аккаунтов не смешивались
        self.account = str(config.get("account", "default"))
        suffix = f"-{self.account}" if self.account and self.account != "default" else ""
        self.log_path = self.log_dir / f"agent{suffix}-{datetime.now():%Y%m%d}.log"
        self.advisor = ClaudeAdvisor(config)
        self.policy = rules.CombatPolicy(config)
        self.stop_after_fights = int(config.get("run", {}).get("stop_after_fights", 0))
        self.fights_done = 0
        self.altar_cache: dict[str, Any] | None = None
        self.altar_checked_at: float = 0.0
        self.idle_sleep = int(config.get("run", {}).get("idle_sleep_sec", 60))
        self.long_idle_sleep = int(config.get("run", {}).get("idle_sleep_no_fights_sec", 900))
        self.action_delay = float(config.get("run", {}).get("action_delay_sec", 1.5))
        # рынок: цены за единицу по ресурсам (серебро) и время последней проверки
        self.market_cache: dict[str, float] = {}
        self.my_lots: list[dict[str, Any]] = []
        self.market_checked_at: float = 0.0
        # фарм-события, которые не удалось запустить (имя -> время до повторной попытки)
        self.farm_cooldown: dict[str, float] = {}
        # колодец удачи и мудрец — тоже кэшируем, чтобы не ходить на страницы каждый цикл
        self.well_cache: dict[str, Any] = {}
        self.well_checked_at: float = 0.0
        self.exp_cache: list[dict[str, Any]] = []
        self.exp_checked_at: float = 0.0
        # прокачка параметров героя: варианты улучшения (/user/master) и кэш
        self.master_cache: list[dict[str, Any]] = []
        self.mastery_cache: dict[str, int] = {}
        self.master_checked_at: float = 0.0
        # текущий режим авторазбора (нужно, чтобы не включать его заново)
        self.autocrack_kind: str = ""
        # крайний срок работы (0 = работаем бесконечно); нужен в облаке,
        # чтобы аккуратно выйти даже посреди боя
        self.deadline: float = 0.0
        # если очко таланта не потратилось (кнопки нет) — не пытаемся заново
        # каждый цикл, иначе агент не доходит до фарма
        self.talent_blocked_until: float = 0.0
        # аналогично для клановых заданий: если «Взять задание» недоступно
        # (задание занято другим игроком), возвращаемся к нему позже
        self.quest_blocked_until: float = 0.0
        # рюкзак: если разгрузить его не вышло (сундук полон и надеть нечего),
        # повторять тот же шаг бессмысленно — он блокирует фарм. Ждём полчаса.
        self.gear_blocked_until: float = 0.0
        self.gear_blocked_sig: tuple[int, int] = (0, 0)
        self.daily = self._load_daily()

    # ------------------------------------------------------------------ логи

    def log(self, message: str, level: str = "INFO") -> None:
        line = f"{datetime.now():%H:%M:%S} [{level}] {message}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8-sig") as fh:
            fh.write(line + "\n")

    # ------------------------------------------------------------------ дневные счётчики

    def daily_path(self) -> Path:
        """Файл дневных счётчиков.

        По умолчанию — рядом с логами. В облаке (GitHub Actions) диск между
        запусками стирается, поэтому счётчики кладутся в отдельный файл
        (`daily_file` в конфиге), который коммитится в репозиторий: без этого
        агент каждый запуск считает, что «сегодня ещё ничего не продавал».
        """
        raw = str(self.config.get("daily_file", "") or "").strip()
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                root = Path(self.config.get("_root") or Path.cwd())
                path = root / path
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        return self.log_dir / "daily.json"

    def _load_daily(self) -> dict[str, Any]:
        """Счётчики за текущие сутки: продажи, покупки опыта, подарок, авторазбор."""
        today = datetime.now().strftime("%Y-%m-%d")
        path = self.daily_path()
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        if data.get("date") != today:
            data = {
                "date": today,
                "sold": 0,
                "exp": 0,
                "gift": False,
                "autocrack": False,
                "award": False,
            }
            self._save_daily(data)
        return data

    def _save_daily(self, data: dict[str, Any] | None = None) -> None:
        data = data or self.daily
        try:
            self.daily_path().write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _bump(self, key: str, value: Any = 1) -> None:
        self.daily = self._load_daily()
        if key in ("gift", "autocrack", "award"):
            self.daily[key] = bool(value)
        else:
            self.daily[key] = int(self.daily.get(key, 0)) + int(value)
        self._save_daily()

    # ------------------------------------------------------------------ цикл

    def run_once(self) -> rules.Decision:
        watchdog = threading.Timer(
            float(self.config.get("run", {}).get("cycle_max_sec", 300)),
            self._abort_cycle,
        )
        watchdog.daemon = True
        watchdog.start()
        try:
            return self._run_once_inner()
        finally:
            watchdog.cancel()

    def _abort_cycle(self) -> None:
        """Сторож: цикл завис — закрываем браузер, агент его перезапустит."""
        self.log("цикл завис дольше лимита — перезапускаю браузер", "WARN")
        try:
            self.game.close()
        except Exception:
            pass

    def _run_once_inner(self) -> rules.Decision:
        if not self.game.browser_alive():
            self.log("браузер закрыт — перезапускаю и вхожу заново", "WARN")
            if not self.game.restart():
                self.log("не удалось восстановить браузер", "ERROR")
                time.sleep(30)
                return rules.Decision("wait", reason="браузер недоступен")
        state = rules.collect_state(self.game, self.config)
        self.last_state = state
        if self.talent_blocked_until > time.time():
            state.talent_points = 0
        state.autocrack_kind = self.autocrack_kind
        if self.quest_blocked_until > time.time():
            state.quests = []
        if self.gear_blocked_until > time.time():
            # пауза действует, только пока содержимое рюкзака/сундука не изменилось:
            # пришёл новый дроп — снова пробуем надеть/разобрать
            sig = (
                int((state.bag or {}).get("bag_used", 0) or 0),
                int((state.bag or {}).get("chest_used", 0) or 0),
            )
            if sig == self.gear_blocked_sig:
                state.gear_blocked = True
            else:
                self.gear_blocked_until = 0.0
        self.daily = self._load_daily()
        state.sold_today = int(self.daily.get("sold", 0))
        state.exp_buys_today = int(self.daily.get("exp", 0))
        state.well_gift_taken_today = bool(self.daily.get("gift", False))
        state.autocrack_set_today = bool(self.daily.get("autocrack", False))
        now = time.time()
        state.farm_skip = [name for name, ts in self.farm_cooldown.items() if ts > now]
        self._check_altar(state)
        self._check_market(state)
        self._check_well(state)
        self._check_exp(state)
        self._check_master(state)
        self._maybe_daily_award()
        self.log("состояние: " + state.summary())

        decision = rules.decide(state, self.config)

        # LLM-советник: подключаем только там, где решение неоднозначно.
        if decision.action == "fight":
            target = self._llm_target(state, decision)
            if target:
                decision = rules.Decision("fight", target=target[0], params={"href": target[1]}, reason="выбор цели по совету LLM")
        if decision.action == "talent":
            self._llm_talent(state)

        self.log(f"решение: {decision.action} {decision.target or ''} — {decision.reason}")
        self._execute(decision, state)
        return decision

    def run_forever(self, max_iterations: int = 0, duration_sec: float = 0.0) -> None:
        """Основной цикл. duration_sec > 0 — аккуратно выйти после указанного времени."""
        iteration = 0
        self.deadline = time.time() + duration_sec if duration_sec else 0.0
        deadline = self.deadline
        self.log("агент запущен")
        while True:
            if deadline and time.time() >= deadline:
                self.log("достигнут лимит времени работы — выхожу")
                break
            iteration += 1
            try:
                decision = self.run_once()
            except Exception as exc:  # не падаем из-за одной ошибки страницы
                self.log(f"ошибка итерации: {exc}", "ERROR")
                time.sleep(10)
                continue
            if max_iterations and iteration >= max_iterations:
                break
            if decision.action == "wait":
                long_wait = bool(decision.params.get("long"))
                seconds = self.long_idle_sleep if long_wait else self.idle_sleep
                if deadline:
                    remaining = deadline - time.time()
                    if remaining <= 5:
                        break
                    seconds = int(min(seconds, max(5, remaining)))
                self.log(f"ожидание {seconds} c")
                time.sleep(seconds)
            else:
                time.sleep(self.action_delay)
                self.game.human.maybe_long_pause()
            if self.stop_after_fights and self.fights_done >= self.stop_after_fights:
                self.log("достигнут лимит боёв для теста, останавливаюсь")
                break

    # ------------------------------------------------------------------ действия

    def _execute(self, decision: rules.Decision, state: rules.GameState) -> None:
        if decision.action == "repair":
            self._do_repair()
        elif decision.action == "altar":
            self._do_altar(decision)
        elif decision.action == "talent":
            self._do_talent(state)
        elif decision.action == "quest":
            self._do_quest(decision)
        elif decision.action == "fight":
            self._do_fight(decision)
        elif decision.action == "donate":
            self._do_donate(decision)
        elif decision.action == "exp":
            self._do_exp(decision)
        elif decision.action == "sell":
            self._do_sell(decision)
        elif decision.action == "well_gift":
            self._do_well_gift()
        elif decision.action == "autocrack":
            self._do_autocrack(decision)
        elif decision.action == "cancel_lot":
            self._do_cancel_lot(decision)
        elif decision.action == "activity":
            self._do_activity(decision)
        elif decision.action == "tower":
            self._do_tower(decision)
        elif decision.action == "gear":
            self._do_gear(decision)
        elif decision.action == "upgrade":
            self._do_upgrade(decision)
        elif decision.action == "upgrade_mastery":
            self._do_upgrade_mastery(decision)
        elif decision.action == "wait":
            time.sleep(2)

    # ------------------------------------------------------------------ башня

    def _maybe_daily_award(self) -> None:
        """Ежедневная награда на главной: у новых героев даёт бесплатный бой."""
        if not self.config.get("daily_award", {}).get("enabled"):
            return
        if self.daily.get("award"):
            return
        try:
            if self.game.claim_daily_award():
                self._bump("award", True)
                self.log("награда: ежедневная награда получена")
            else:
                self.log("награда: ежедневная награда недоступна")
        except Exception as exc:
            self.log(f"награда: не удалось получить — {exc}", "WARN")

    def _do_gear(self, decision: rules.Decision) -> None:
        """Рюкзак: сначала надеть «Лучше», потом разобрать остальное на железо.

        Порядок именно такой: вещь с пометкой «Лучше (+N)» сильнее надетой,
        её надо надеть, а уже всё остальное можно превратить в железо.
        """
        keep = int(decision.params.get("keep_bag", 4))
        max_equip = int(decision.params.get("max_equip", 8))
        crack = bool(decision.params.get("crack", True))
        worn = self.game.equip_better_items(limit=max_equip)
        cracked = 0
        moved = 0
        if crack:
            # разбираем всё, кроме «Лучше» — эти вещи уже надеты выше
            cracked = self.game.crack_items(limit=int(self.config.get("gear", {}).get("crack_limit", 25)))
            # остаток (уже надетые дубли/хлам без «Лучше») — в сундук, если есть место
            moved = self.game.stash_items(keep=keep)
        else:
            moved = self.game.stash_items(keep=keep)
        counts = self.game.bag_counts()
        self.log(
            f"рюкзак: надето {worn}, разобрано {cracked}, в сундук {moved}, "
            f"рюкзак {counts.get('bag_used')}/{counts.get('bag_total')}, "
            f"сундук {counts.get('chest_used')}/{counts.get('chest_total')}"
        )
        if worn == 0 and cracked == 0 and moved == 0:
            # Ничего не изменилось: сундук полон и надеть нечего. Повторять
            # этот шаг бессмысленно — он блокирует фарм, поэтому ставим паузу.
            self.gear_blocked_until = time.time() + 1800
            self.gear_blocked_sig = (
                int(counts.get("bag_used", 0) or 0),
                int(counts.get("chest_used", 0) or 0),
            )
            self.log(
                "рюкзак разгрузить не удалось (нечего надеть и нечего разобрать) — "
                "ждём 30 мин, идём фармить",
                "WARN",
            )

    def _do_upgrade_mastery(self, decision: rules.Decision) -> None:
        """Повышение уровня мастерства: железо + мифрил (постоянный бонус)."""
        iron = int(decision.params.get("iron", 0))
        mifril = int(decision.params.get("mifril", 0))
        if self.game.upgrade_mastery_level():
            self._bump("upgrade")
            self.log(f"прокачка: уровень мастерства повышен (за {iron} железа и {mifril} мифрила)")
        else:
            self.log("прокачка: повысить мастерство не удалось", "WARN")
            self.master_checked_at = 0.0

    def _do_upgrade(self, decision: rules.Decision) -> None:
        """Прокачка параметра героя железом (/user/master)."""
        href = str(decision.params.get("href", ""))
        param = decision.target or "?"
        cost = int(decision.params.get("cost", 0))
        if not href:
            self.log("прокачка: нет ссылки на улучшение", "WARN")
            return
        if self.game.upgrade_master_param(href):
            self._bump("upgrade")
            self.log(f"прокачка: параметр {param} улучшен за {cost} железа")
        else:
            self.log(f"прокачка: улучшить {param} не удалось", "WARN")
            self.master_checked_at = 0.0

    def _do_tower(self, decision: rules.Decision) -> None:
        """Фарм башни: бесплатный бой, капает опыт, железо, бутылочки и вещи."""
        rounds = int(decision.params.get("rounds", 3))
        name = self.game.open_tower()
        if not name:
            self.log("башня: не удалось открыть локацию", "WARN")
            return
        for index in range(max(1, rounds)):
            outcome = self._fight_loop()
            self.log(f"башня «{name}»: раунд {index + 1}/{rounds} — {outcome}")
            if outcome in ("прервано", "отступление", "таймаут"):
                break
            if not self.game.has_attack():
                break
        self.fights_done += 1
        self.game.click_text("Покинуть бой")

    # ------------------------------------------------------------------ торговля

    def _check_market(self, state: rules.GameState) -> None:
        """Раз в market_check_interval_min смотрим цены на аукционе ресурсов."""
        interval = float(self.config.get("market", {}).get("check_interval_min", 30)) * 60
        now = time.time()
        if self.market_checked_at and now - self.market_checked_at < interval:
            state.market_prices = dict(self.market_cache)
            state.my_lots = list(self.my_lots)
            state.market_checked = True
            return
        prices: dict[str, float] = {}
        my_lots: list[dict[str, Any]] = []
        try:
            # свои лоты — одна страница «Мои лоты» на все ресурсы
            if self.game.open_bazaar_tab("mine"):
                html = self.game.p.content()
                for resource in ("bottles", "mifril"):
                    for lot in pages.parse_lots(html, resource):
                        lot["resource"] = resource
                        my_lots.append(lot)
            for resource, tab in (("bottles", "bottles"), ("mifril", "mifril")):
                if not self.game.open_bazaar_tab(tab):
                    continue
                lots = pages.bazaar_lots(self.game, resource)
                best = pages.median_unit_price(lots)
                if best:
                    prices[resource] = best
        except Exception as exc:
            self.log(f"рынок: не удалось прочитать цены: {exc}", "WARN")
        self.market_cache = prices
        self.my_lots = my_lots
        self.market_checked_at = now
        state.market_prices = dict(prices)
        state.my_lots = list(my_lots)
        state.market_checked = True
        if prices:
            pretty = ", ".join(f"{k}={v:.3f} сер/шт" for k, v in prices.items())
            self.log(f"рынок: лучшие цены — {pretty}")
        if my_lots:
            detail = ", ".join(
                f"{lot['resource']}×{lot['amount']} по {lot['unit_price_silver']:.2f} сер/шт"
                for lot in my_lots
            )
            self.log(f"аукцион: наши лоты — {detail}")

    def _check_well(self, state: rules.GameState) -> None:
        """Раз в час проверяем колодец удачи: доступен ли бесплатный подарок."""
        interval = float(self.config.get("well", {}).get("check_interval_min", 60)) * 60
        now = time.time()
        if self.well_checked_at and now - self.well_checked_at < interval:
            state.well_gift_available = bool(self.well_cache.get("gift_available"))
            return
        try:
            self.game.goto("https://barbars.ru/trade/well")
            self.well_cache = pages.well_state(self.game)
        except Exception as exc:
            self.log(f"колодец: проверка не удалась: {exc}", "WARN")
            return
        self.well_checked_at = now
        state.well_gift_available = bool(self.well_cache.get("gift_available"))
        if state.well_gift_available and not state.well_gift_taken_today:
            self.log("колодец: доступен бесплатный ежедневный подарок")

    def _check_exp(self, state: rules.GameState) -> None:
        """Раз в час читаем варианты покупки опыта у мудреца."""
        interval = float(self.config.get("exp", {}).get("check_interval_min", 60)) * 60
        now = time.time()
        if self.exp_checked_at and now - self.exp_checked_at < interval:
            state.exp_options = list(self.exp_cache)
            return
        try:
            self.game.goto("https://barbars.ru/trade/ironmaster")
            self.exp_cache = pages.ironmaster_options(self.game)
        except Exception as exc:
            self.log(f"мудрец: проверка не удалась: {exc}", "WARN")
            return
        self.exp_checked_at = now
        state.exp_options = list(self.exp_cache)

    def _check_master(self, state: rules.GameState) -> None:
        """Раз в 10 минут читаем варианты прокачки параметров героя (/user/master).

        По правилу игрока железо тратится на прокачку. Золотые варианты
        (у keis параметры стоят золота) пропускаются — золото не тратим.
        """
        if not self.config.get("upgrade", {}).get("enabled"):
            return
        interval = float(self.config.get("upgrade", {}).get("check_interval_min", 10)) * 60
        now = time.time()
        if self.master_checked_at and now - self.master_checked_at < interval:
            state.master_options = list(self.master_cache)
            state.mastery_cost = dict(self.mastery_cache)
            return
        try:
            info = self.game.master_state()
        except Exception as exc:
            self.log(f"прокачка: не удалось прочитать варианты: {exc}", "WARN")
            return
        self.master_cache = list(info.get("params", []))
        self.mastery_cache = dict(info.get("mastery", {}))
        self.master_checked_at = now
        state.master_options = list(self.master_cache)
        state.mastery_cost = dict(info.get("mastery", {}))
        iron_opts = [o for o in self.master_cache if o.get("currency") == "iron"]
        if iron_opts:
            self.log(
                "прокачка: железные варианты — "
                + ", ".join(f"{o['param']}+{o.get('gain', 1)} за {o['cost']}" for o in iron_opts)
            )
        if state.mastery_cost:
            self.log(
                "прокачка: уровень мастерства — "
                + ", ".join(f"{k} {v}" for k, v in state.mastery_cost.items())
            )

    def _do_exp(self, decision: rules.Decision) -> None:
        """Покупка опыта у мудреца за железо (золото не трогаем)."""
        amount = int(decision.params.get("amount", 0))
        result = self.game.buy_exp_with_iron(amount)
        if result.get("ok"):
            self._bump("exp")
            self.log(f"мудрец: куплен опыт за {amount} железа ({decision.params.get('percent')}% прокачки)")
        else:
            self.log(f"мудрец: покупка опыта не удалась — {result.get('message')}", "WARN")

    def _do_sell(self, decision: rules.Decision) -> None:
        """Выставление лота на аукционе ресурсов (мифрил/бутылочки)."""
        resource = decision.target or "bottles"
        amount = int(decision.params.get("amount", 0))
        gold = int(decision.params.get("gold", 0))
        silver = int(decision.params.get("silver", 0))
        result = self.game.sell_resource(resource, amount, gold, silver)
        if result.get("ok"):
            self._bump("sold")
            self.log(f"аукцион: {result.get('message')}")
        else:
            self.log(f"аукцион: лот не выставлен — {result.get('message')}", "WARN")
            self.game.dump_page("bazaar-lot-failed", self.log_dir)

    def _do_well_gift(self) -> None:
        """Бесплатный ежедневный подарок колодца удачи."""
        if self.game.well_daily_gift():
            self._bump("gift", True)
            self.log("колодец: подарок получен")
        else:
            self.log("колодец: подарок получить не удалось", "WARN")
            self.well_checked_at = 0.0

    def _do_autocrack(self, decision: rules.Decision) -> None:
        """Включение авторазбора вещей в железо (и мифрил, если есть профессия)."""
        kind = decision.target or "autoCrackCommonLink"
        if self.game.set_autocrack(kind):
            self._bump("autocrack", True)
            self.autocrack_kind = kind
            self.log(f"авторазбор: включён режим {kind}")
        else:
            self.log("авторазбор: переключатель не найден", "WARN")

    def _do_cancel_lot(self, decision: rules.Decision) -> None:
        """Снять свой лот, если рынок просел."""
        resource = decision.target or "bottles"
        if self.game.cancel_lot(resource):
            self.log(f"аукцион: лот {resource} снят")
            self.market_checked_at = 0.0
        else:
            self.log(f"аукцион: не удалось снять лот {resource}", "WARN")

    def _do_activity(self, decision: rules.Decision) -> None:
        """Фарм-событие: зайти в активность и подраться, если противник появился."""
        name = decision.target or "событие"
        url = decision.params.get("url", "")
        wait_sec = int(decision.params.get("wait_sec", 120))
        result = self.game.enter_activity(url, wait_sec=wait_sec)
        if not result.get("ok"):
            note = result.get("note") or result.get("stage") or "недоступно"
            retry = float(self.config.get("farm", {}).get("retry_min", 30))
            self.farm_cooldown[name] = time.time() + retry * 60
            self.log(f"событие «{name}» недоступно: {note} (пропустим {retry} мин)", "INFO")
            self.game.click_text("Покинуть бой")
            return
        self.farm_cooldown.pop(name, None)
        self.log(f"событие «{name}»: бой начался ({result.get('stage')})")
        outcome = self._fight_loop()
        self.fights_done += 1
        self.log(f"событие «{name}»: бой завершён — {outcome}")
        self.game.click_text("Покинуть бой")

    def _do_repair(self) -> None:
        hero_id = self.game.hero_id
        if hero_id:
            self.game.goto(f"user/body/id/{hero_id}")
        if self.game.repair_all():
            self.log("снаряжение починено")
        else:
            self.log("починка не потребовалась (нет кнопки)")

    def _check_altar(self, state: rules.GameState) -> None:
        """Раз в check_interval_min смотрим алтарь: бонус и когда он протухнет."""
        now = time.time()
        interval = float(self.config.get("altar", {}).get("check_interval_min", 30)) * 60
        if self.altar_checked_at and now - self.altar_checked_at < interval:
            if self.altar_cache:
                state.altar_bonus = self.altar_cache.get("bonus")
                state.altar_expires_in_min = self.altar_cache.get("expires_in_min")
                state.altar_options = self.altar_cache.get("options", [])
            return
        if not self.game.ensure_guild_id():
            return
        self.game.goto(f"guild/altar/0/{self.game.guild_id}")
        info = pages.altar_info(self.game)
        self.altar_cache = info
        self.altar_checked_at = now
        state.altar_bonus = info.get("bonus")
        state.altar_expires_in_min = info.get("expires_in_min")
        state.altar_options = info.get("options", [])
        self.log(
            f"алтарь: бонус +{info.get('bonus')}% "
            f"(осталось {info.get('expires_in_min')} мин), доступно: "
            f"{[(o['kind'], o['cost']) for o in info.get('options', [])]}"
        )

    def _do_altar(self, decision: rules.Decision) -> None:
        """Пожертвование в алтарь клана — бонус ко всем параметрам."""
        resource = decision.target or "iron"
        amount = decision.params.get("amount")
        result = self.game.activate_altar(resource=resource, amount=amount)
        if result.get("ok"):
            self.log(
                f"алтарь: пожертвовано {result.get('cost')} ({resource}), "
                f"бонус клана +{result.get('bonus')}%"
            )
            self.altar_checked_at = 0.0  # сброс кэша — состояние изменилось
        else:
            self.log("алтарь: пожертвование не выполнено (вариант сейчас недоступен)")
            self.altar_checked_at = 0.0

    def _do_talent(self, state: rules.GameState) -> None:
        self.game.goto("user/stances")
        available = [t for t in pages.talents(self.game) if not t.studied]
        if not available:
            self.log("нет доступных талантов")
            return
        priority = self.config.get("talent_priority", [])
        candidates: list[pages.Talent] = []
        for want in priority:
            for t in available:
                if t.name.lower() == want.lower() and t not in candidates:
                    candidates.append(t)
        if self.advisor.available():
            try:
                suggestion = self.advisor.choose_talent(state.summary(), [vars(t) for t in available])
                if suggestion:
                    self.log(f"LLM советует талант: {suggestion}")
                    for t in available:
                        if t.name.lower() == suggestion.lower() and t not in candidates:
                            candidates.insert(0, t)
            except Exception as exc:
                self.log(f"LLM-совет по талантам не удался: {exc}", "WARN")
        for t in available:
            if t not in candidates:
                candidates.append(t)

        for talent in candidates[:4]:
            ok, detail = self.game.spend_talent(talent.name)
            if ok:
                self.log(f"талант улучшен: {talent.name} ({detail})")
                return
            self.log(f"талант {talent.name} не изучен: {detail}")
        self.log("не удалось потратить очко таланта — вернусь к талантам позже")
        self.talent_blocked_until = time.time() + 1800

    def _do_quest(self, decision: rules.Decision) -> None:
        if not self.game.guild_id:
            self.log("нет клана — задание взять некуда")
            return
        self.game.goto(f"guild/quests/0/{self.game.guild_id}")
        index = int(decision.params.get("index", 0))
        if self.game.take_clan_quest(index):
            self.log(f"взято клановое задание: {decision.target}")
        else:
            self.quest_blocked_until = time.time() + 900
            self.log("задание не взято (кнопка не найдена) — вернусь к заданиям через 15 мин")

    def _do_fight(self, decision: rules.Decision) -> None:
        href = decision.params.get("href")
        if not href:
            self.log("нет ссылки на бой")
            return
        self.game.goto(href)
        result = self._fight_loop()
        self.fights_done += 1
        self.log(f"бой «{decision.target}» завершён: {result}")
        # выходим из боя на главную, чтобы состояние обновилось
        self.game.click_text("Покинуть бой")

    def _fight_loop(self) -> str:
        turns = 0
        max_turns = int(self.config.get("fight", {}).get("max_turns", 80))
        last_log = ""
        stale_energy_checks = 0
        last_energy = None
        while turns < max_turns:
            if self.deadline and time.time() >= self.deadline:
                self.log("  выходим по лимиту времени")
                return "время вышло"
            cs = self.game.combat()
            if cs.log_lines:
                new_log = cs.log_lines[-1]
                if new_log != last_log:
                    self.log(f"  ход {turns}: {new_log}")
                    last_log = new_log
            if cs.victory is not None:
                return "победа" if cs.victory else "поражение"
            if cs.finished and not cs.attack_links:
                self.log("  бой окончен")
                return "окончен"
            status = self.game.status()
            base = self.last_state or rules.GameState()
            state = rules.GameState(
                max_hp=base.max_hp or cs.our_hp or status.hp,
                max_energy=base.max_energy or cs.our_energy or status.energy,
            )
            decision = self.policy.choose(cs, status, state)
            self.game.human.pause("fight")
            if decision.action == "attack":
                turns += 1
                if not self.game.click_attack():
                    self.log("  не удалось ударить")
                    return "прервано"
            elif decision.action == "ability":
                turns += 1
                self.game.use_ability(decision.params.get("href", ""))
                self.log(f"  умение: {decision.target}")
            elif decision.action == "potion":
                turns += 1
                self.game.click_text(decision.params.get("text", ""))
                self.log("  выпили зелье")
            elif decision.action == "heal":
                turns += 1
                self.game.click_text(decision.params.get("text", ""))
                self.log("  вылечил союзника")
            elif decision.action == "flee":
                self.game.click_text(decision.params.get("text", ""))
                self.log("  отступил")
                return "отступление"
            elif decision.action == "wait_energy":
                turns += 1  # иначе ожидание энергии может длиться вечно
                # Энергия капает на сервере, но в HTML обновляется только при
                # перезагрузке страницы — иначе цикл зависает на старом значении.
                energy_now = cs.our_energy or 0
                if last_energy is not None and energy_now <= last_energy:
                    stale_energy_checks += 1
                else:
                    stale_energy_checks = 0
                last_energy = energy_now
                self.game.reload()
                time.sleep(self.config.get("fight", {}).get("energy_wait_sec", 3))
                if stale_energy_checks >= 3:
                    self.log("  энергия не растёт — бьём принудительно")
                    if not self.game.click_attack():
                        return "прервано"
            else:
                time.sleep(2)
        return "таймаут"

    def _do_donate(self, decision: rules.Decision) -> None:
        if not self.game.guild_id:
            return
        donate_cfg = self.config.get("spend", {}).get("clan_donate", {})
        kind = decision.target or "iron"
        amount = donate_cfg.get("iron_amount", 50_000)
        given = self.game.donate_clan(kind, amount=amount)
        if given:
            self.log(f"в клан вложено: {given} {kind}")
        else:
            self.log("вклад не выполнен — нет подходящей кнопки, страница сохранена")
            self.game.dump_page("clan-donate-unknown", self.log_dir)

    # ------------------------------------------------------------------ LLM

    def _llm_target(self, state: rules.GameState, decision: rules.Decision) -> tuple[str, str] | None:
        if not self.advisor.available():
            return None
        options = [
            {"title": t.title, "href": t.href, "note": f"осталось боёв: {t.fights_left}, тип: {t.kind}"}
            for t in state.targets
        ]
        if len(options) < 2:
            return None
        href = self.advisor.choose_target(state.summary(), options)
        if not href:
            return None
        for t in state.targets:
            if t.href == href:
                self.log(f"LLM выбрала цель: {t.title}")
                return t.title, href
        return None

    def _llm_talent(self, state: rules.GameState) -> None:
        """Подсказка LLM записывается в лог, выбор остаётся за приоритетом."""
        if not self.advisor.available():
            return
        try:
            self.game.goto("user/stances")
            available = [vars(t) for t in pages.talents(self.game) if not t.studied]
            if available:
                choice = self.advisor.choose_talent(state.summary(), available)
                if choice:
                    self.log(f"LLM советует талант: {choice}")
        except Exception as exc:
            self.log(f"LLM-совет по талантам не удался: {exc}", "WARN")

    # ------------------------------------------------------------------ отчёт

    def dump_state(self) -> None:
        snapshot = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "status": self.game.status().as_dict(),
        }
        path = self.log_dir / "last-state.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
