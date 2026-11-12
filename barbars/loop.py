"""Основной цикл агента: сбор состояния -> решение -> действие -> повтор."""

from __future__ import annotations

import json
import re
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
        # сколько боёв подряд прошло в каждом событии (нужно для ротации)
        self.farm_streak: dict[str, int] = {}
        # состояние Полей сражений между проверками (кэш)
        self.battlefields_cache: dict[str, Any] = {}
        # зал кланового босса: кэш состояния и время последней проверки
        self.raid_cache: dict[str, Any] = {}
        self.raid_checked_at: float = 0.0
        self.raid_last_at: float = 0.0
        # сколько урона нанесли в последнем бою (для замера по боссу)
        self.last_damage: int = 0
        # идёт ли сейчас длинная операция (рейд) — сторож цикла её не рвёт
        self.in_long_op: bool = False
        self._watchdog: threading.Timer | None = None
        # счётчик боёв в событиях: по нему чередуем башню, чтобы она была фоном
        self.activity_fights = 0
        # колодец удачи и мудрец — тоже кэшируем, чтобы не ходить на страницы каждый цикл
        self.well_cache: dict[str, Any] = {}
        self.well_checked_at: float = 0.0
        self.exp_cache: list[dict[str, Any]] = []
        self.exp_checked_at: float = 0.0
        # прокачка параметров героя: варианты улучшения (/user/master) и кэш
        self.master_cache: list[dict[str, Any]] = []
        self.mastery_cache: dict[str, int] = {}
        self.master_checked_at: float = 0.0
        # почта: есть ли что забрать (проверяем не каждый цикл)
        self.mail_checked_at: float = 0.0
        self.mail_pending: bool = False
        # аукцион вещей и рынок лотов — тоже раз в несколько минут
        self.auction_checked_at: float = 0.0
        self.trade_market_checked_at: float = 0.0
        # магазин снаряжения — тоже не каждый цикл
        self.shop_checked_at: float = 0.0
        # поля сражений и свитки — тоже с интервалом
        self.battlefields_checked_at: float = 0.0
        self.scrolls_checked_at: float = 0.0
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
            # купленные слоты и вещи не сбрасываем: вещи покупаются один раз
            bought = data.get("shop_slots", []) or []
            bought_items = data.get("shop_bought", []) or []
            data = {
                "date": today,
                "sold": 0,
                "exp": 0,
                "gift": False,
                "autocrack": False,
                "award": False,
                "auction": 0,
                "market": 0,
                "market_bought": [],
                "shop_buy_ids": [],
                "shop_slots": bought,
                "shop_bought": bought_items,
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
        limit = float(self.config.get("run", {}).get("cycle_max_sec", 300))
        self._watchdog = threading.Timer(limit, self._abort_cycle)
        self._watchdog.daemon = True
        self._watchdog.start()
        try:
            return self._run_once_inner()
        finally:
            if self._watchdog:
                self._watchdog.cancel()
            self._watchdog = None

    def _abort_cycle(self) -> None:
        """Сторож: цикл завис — закрываем браузер, агент его перезапустит.

        Во время длинных операций (рейд в зале босса) убивать браузер нельзя:
        цикл рейда штатно длиннее лимита цикла, а закрытие браузера из
        отдельного потока рвёт соединение Playwright. В таком случае просто
        перевзводим сторож и ждём дальше.
        """
        if self.in_long_op:
            self.log("цикл идёт дольше лимита (длинная операция) — продолжаем", "WARN")
            limit = float(self.config.get("run", {}).get("cycle_max_sec", 300))
            self._watchdog = threading.Timer(limit, self._abort_cycle)
            self._watchdog.daemon = True
            self._watchdog.start()
            return
        self.log("цикл завис дольше лимита — перезапускаю браузер", "WARN")
        try:
            self.game.close()
        except Exception:
            pass

    def _gated_config(self, now: float) -> dict[str, Any]:
        """Конфиг для текущего цикла: магазин снаряжения смотрим не каждый раз.

        Иначе агент тратит по несколько заходов на страницы магазина в каждом
        цикле, а там всё равно ничего нового не появилось.
        """
        cfg = dict(self.config)
        shop_cfg = dict(cfg.get("shop", {}) or {})
        interval = float(shop_cfg.get("check_interval_min", 30)) * 60
        if (now - self.shop_checked_at) < interval:
            shop_cfg["enabled"] = False
        cfg["shop"] = shop_cfg
        return cfg

    def _run_once_inner(self) -> rules.Decision:
        if not self.game.browser_alive():
            self.log("браузер закрыт — перезапускаю и вхожу заново", "WARN")
            if not self.game.restart():
                self.log("не удалось восстановить браузер", "ERROR")
                time.sleep(30)
                return rules.Decision("wait", reason="браузер недоступен")
        now = time.time()
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
        state.shop_slots = list(self.daily.get("shop_slots", []) or [])
        state.shop_bought = list(self.daily.get("shop_bought", []) or [])
        state.auction_today = int(self.daily.get("auction", 0) or 0)
        state.market_today = int(self.daily.get("market", 0) or 0)
        state.exp_buys_today = int(self.daily.get("exp", 0))
        state.well_gift_taken_today = bool(self.daily.get("gift", False))
        state.autocrack_set_today = bool(self.daily.get("autocrack", False))
        state.raid_last_at = float(self.daily.get("raid_last_at", 0.0) or 0.0)
        state.raid_today = int(self.daily.get("raid", 0) or 0)
        now = time.time()
        state.farm_skip = [name for name, ts in self.farm_cooldown.items() if ts > now]
        self._check_altar(state)
        self._check_market(state)
        self._check_auction(state)
        self._check_trade_market(state)
        self._check_battlefields(state)
        self._check_raid(state)
        self._check_scrolls(state)
        self._check_well(state)
        self._check_exp(state)
        self._check_master(state)
        self._check_mail(state)
        self._maybe_daily_award()
        self.log("состояние: " + state.summary())

        decision = rules.decide(state, self._gated_config(now))

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
        elif decision.action == "shop":
            self._do_shop(decision, state)
            self.shop_checked_at = time.time()
        elif decision.action == "share_money":
            self._do_share_money(decision)
        elif decision.action == "share_gear":
            self._do_share_gear(decision)
        elif decision.action == "auction":
            self._do_auction(decision, state)
            self.auction_checked_at = time.time()
        elif decision.action == "trade_market":
            self._do_trade_market(decision, state)
            self.trade_market_checked_at = time.time()
        elif decision.action == "battlefields":
            self._do_battlefields(decision)
        elif decision.action == "raid":
            self._do_raid(decision, state)
        elif decision.action == "ability":
            self._do_ability(decision)
        elif decision.action == "scrolls":
            self._do_scrolls(decision, state)
        elif decision.action == "mail":
            self._do_mail()
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
        """Рюкзак: надеть «Лучше», разобрать остальное на железо, лишнее — на витрину.

        Порядок именно такой: вещь с пометкой «Лучше (+N)» сильнее надетой,
        её надо надеть; остальное (кроме мифических) превращаем в железо;
        мифические, которые не надели, выставляем на «Витрину клана» —
        это единственный способ продать снаряжение (обычный аукцион — только
        для ресурсов).
        """
        keep = int(decision.params.get("keep_bag", 4))
        max_equip = int(decision.params.get("max_equip", 8))
        crack = bool(decision.params.get("crack", True))
        sell_store = bool(decision.params.get("sell_store", True))
        gear_cfg = self.config.get("gear", {})
        worn = self.game.equip_better_items(limit=max_equip)
        cracked = 0
        moved = 0
        sold = 0
        if crack:
            # разбираем всё, кроме «Лучше» (их надо надеть) и мифических
            cracked = self.game.crack_items(
                limit=int(gear_cfg.get("crack_limit", 10)),
                keep_better=True,
                keep_mythic=bool(gear_cfg.get("keep_mythic", True)),
            )
            # сундук: там копится старый хлам (1-11 ур), разбираем его со
            # страницы вещи — иначе место для нового дропа закончится
            if bool(gear_cfg.get("crack_chest", True)):
                chest_cracked = self.game.crack_chest_items(
                    limit=int(gear_cfg.get("crack_chest_limit", 15)),
                    keep_mythic=bool(gear_cfg.get("keep_mythic", True)),
                    keep_better=True,
                )
                cracked += chest_cracked
        counts = self.game.bag_counts()
        # лишние мифические вещи (дубли по слотам) — на витрину, их не разобрать
        sold = 0
        if sell_store:
            sold = self.game.sell_duplicate_items(limit=int(gear_cfg.get("sell_limit", 3)))
        # рюкзак переполнен, а надеть/сломать больше нечего — часть вещей
        # (мифические, не поместившиеся в снаряжение) продаём на витрине клана
        if sell_store and int(counts.get("bag_used", 0) or 0) >= int(counts.get("bag_total", 20) or 20):
            sold += self.game.sell_extra_items(limit=int(gear_cfg.get("sell_limit", 3)))
        moved = self.game.stash_items(keep=keep)
        counts = self.game.bag_counts()
        self.log(
            f"рюкзак: надето {worn}, разобрано {cracked}, на витрину {sold}, в сундук {moved}, "
            f"рюкзак {counts.get('bag_used')}/{counts.get('bag_total')}, "
            f"сундук {counts.get('chest_used')}/{counts.get('chest_total')}"
        )
        if worn == 0 and cracked == 0 and moved == 0 and sold == 0:
            # Ничего не изменилось: сундук полон и надеть нечего. Повторять
            # этот шаг бессмысленно — он блокирует фарм, поэтому ставим паузу.
            pause_min = int(gear_cfg.get("pause_min", 10))
            self.gear_blocked_until = time.time() + pause_min * 60
            self.gear_blocked_sig = (
                int(counts.get("bag_used", 0) or 0),
                int(counts.get("chest_used", 0) or 0),
            )
            self.log(
                "рюкзак разгрузить не удалось (нечего надеть и нечего разобрать) — "
                f"ждём {pause_min} мин, идём фармить",
                "WARN",
            )

    def _do_share_gear(self, decision: rules.Decision) -> None:
        """Отправить купленное снаряжение другому герою (витрина -> почта)."""
        recipient = str(decision.target or "")
        item_ids = [str(i) for i in decision.params.get("items", []) or []]
        if not recipient or not item_ids:
            return
        try:
            in_bag = set(self.game.bag_item_ids())
            todo = [i for i in item_ids if i in in_bag]
            if not todo:
                return
            # витрина должна содержать только передаваемые вещи
            self.game.store_take_all()
            for item_id in todo:
                if not self.game.sell_item_to_store(item_id):
                    self.log("передача: не удалось выложить вещь на витрину", "WARN")
                    return
            if self.game.send_store_items_to(recipient, "Снаряжение 25 уровня"):
                self.log(f"передача: отправлено получателю {recipient} — {len(todo)} шт.")
                # отправленные вещи больше не наши
                left = [i for i in item_ids if i not in todo]
                self.daily = self._load_daily()
                self.daily["shop_bought"] = left
                self._save_daily()
            else:
                self.log("передача: отправить не удалось", "WARN")
        except Exception as exc:
            self.log(f"передача: ошибка — {exc}", "WARN")

    def _do_share_money(self, decision: rules.Decision) -> None:
        """Передать золото/серебро другому герою письмом."""
        recipient = str(decision.target or "")
        gold = int(decision.params.get("gold", 0))
        silver = int(decision.params.get("silver", 0))
        if not recipient:
            return
        if self.game.send_money_to(recipient, gold=gold, silver=silver):
            self.log(f"передача: отправлено {recipient} — {gold} золота, {silver} серебра")
        else:
            self.log(f"передача: не удалось отправить {gold} золота / {silver} серебра", "WARN")

    def _do_mail(self) -> None:
        """Забрать почту (присланные вещи/деньги) и надеть присланное."""
        if not self.game.take_mail():
            self.log("почта: забрать не удалось", "WARN")
            self.mail_checked_at = 0.0
            return
        self.mail_pending = False
        self.log("почта: письма забраны")
        worn = self.game.equip_better_items(limit=int(self.config.get("gear", {}).get("max_equip", 8)))
        if worn:
            self.log(f"почта: надето присланных вещей {worn}")

    def _check_auction(self, state: rules.GameState) -> None:
        """Ищем дубли мифических вещей — их можно продать лотом.

        Дубль — вещь, слот которой уже занят надетой. Такие вещи не нужны
        герою, а разобрать их нельзя (мифические), поэтому продаём.
        """
        from . import pages

        cfg = self.config.get("auction", {}) or {}
        if not cfg.get("enabled"):
            return
        now = time.time()
        if (now - self.auction_checked_at) < float(cfg.get("check_interval_min", 30)) * 60:
            return
        self.auction_checked_at = now
        try:
            bag = self.game.bag_items()
            worn = self.game.worn_gear()
        except Exception as exc:
            self.log(f"аукцион: рюкзак не прочитан: {exc}", "WARN")
            return
        busy: dict[str, str] = {}
        for w in worn:
            slot, _kind = pages.slot_of(w.get("name", ""))
            if slot:
                busy[slot] = w.get("name", "")
        duplicates: list[dict[str, Any]] = []
        for item in bag:
            name = str(item.get("name", "") or "")
            if not name or item.get("personal") or not item.get("mythic"):
                continue
            slot, _kind = pages.slot_of(name)
            if not slot or slot not in busy:
                continue
            duplicates.append(item)
        state.duplicates = duplicates
        if duplicates:
            names = ", ".join(str(d.get("name", "")) for d in duplicates[:4])
            self.log(f"аукцион: дублей в рюкзаке — {len(duplicates)} ({names})")

    def _check_trade_market(self, state: rules.GameState) -> None:
        """Проверяем, нужны ли нужному герою вещи с рынка аукционов."""
        from . import pages

        cfg = self.config.get("trade_market", {}) or {}
        if not cfg.get("enabled"):
            return
        now = time.time()
        if (now - self.trade_market_checked_at) < float(cfg.get("check_interval_min", 60)) * 60:
            return
        self.trade_market_checked_at = now
        for_hero = str(cfg.get("for_hero", "") or "")
        if not for_hero:
            return
        min_level = int(cfg.get("min_level", 25))
        try:
            gear = self.game.other_hero_gear(for_hero)
        except Exception as exc:
            self.log(f"рынок: снаряжение героя {for_hero} не прочитано: {exc}", "WARN")
            return
        state.target_gear = gear
        worn_slots: dict[str, int] = {}
        for w in gear:
            slot, _kind = pages.slot_of(w.get("name", ""))
            if slot:
                worn_slots[slot] = int(w.get("level", 0) or 0)
        need = [s for s, lvl in worn_slots.items() if lvl < min_level]
        missing = [
            s
            for s in (
                "шлем", "амулет", "наплечники", "накидка", "броня", "пояс",
                "штаны", "браслеты", "перчатки", "кольцо", "оружие", "обувь",
            )
            if s not in worn_slots
        ]
        state.market_due = bool(need or missing)
        if state.market_due:
            self.log(
                f"рынок: герою {for_hero} нужны вещи — пустые слоты: "
                f"{', '.join(missing) or 'нет'}, слабые: {', '.join(need) or 'нет'}"
            )

    def _check_battlefields(self, state: rules.GameState) -> None:
        """Поля сражений: когда бой и сколько очков полей накоплено."""
        cfg = self.config.get("battlefields", {}) or {}
        if not cfg.get("enabled"):
            return
        now = time.time()
        if (now - self.battlefields_checked_at) < float(cfg.get("check_interval_min", 5)) * 60:
            # между проверками отдаём кэш: иначе герой ждал бы старта боя
            # лишние 5 минут, а бой на полях идёт недолго
            state.battlefields = self.battlefields_cache
            state.bg_points = int(self.battlefields_cache.get("points", 0) or 0)
            return
        self.battlefields_checked_at = now
        try:
            info = self.game.battlefields_state()
        except Exception as exc:
            self.log(f"поля сражений: не удалось проверить: {exc}", "WARN")
            state.battlefields = self.battlefields_cache
            return
        self.battlefields_cache = info
        state.battlefields = info
        state.bg_points = int(info.get("points", 0) or 0)
        countdown = str(info.get("countdown", "") or "")
        self.log(
            "поля сражений: "
            + (f"бой через {countdown}" if countdown else "бой идёт")
            + f", очков полей {state.bg_points}, боёв сегодня {info.get('fights_today', 0)}"
        )

    def _check_scrolls(self, state: rules.GameState) -> None:
        """Ищем свитки и книги, которые можно активировать."""
        cfg = self.config.get("scrolls", {}) or {}
        if not cfg.get("enabled"):
            return
        now = time.time()
        if (now - self.scrolls_checked_at) < float(cfg.get("check_interval_min", 10)) * 60:
            return
        self.scrolls_checked_at = now
        try:
            scrolls = self.game.scroll_items()
        except Exception as exc:
            self.log(f"свитки: рюкзак не прочитан: {exc}", "WARN")
            return
        state.scrolls = scrolls
        if scrolls:
            self.log(f"свитки: найдено {len(scrolls)} — {', '.join(s['name'] for s in scrolls[:4])}")

    def _do_battlefields(self, decision: rules.Decision) -> None:
        """Бой на Полях сражений — за победу дают очки полей."""
        self.game.goto(str(decision.params.get("url", "https://barbars.ru/game/bg")))
        if not self.game.join_battlefields():
            info = self.game.battlefields_state()
            countdown = str(info.get("countdown", "") or "")
            self.log(f"поля сражений: вступить нельзя (отсчёт {countdown or '—'})", "INFO")
            return
        outcome = self._fight_loop()
        self.fights_done += 1
        self.log(f"поля сражений: бой завершён — {outcome}")
        self.game.click_text("Покинуть бой")

    def _do_ability(self, decision: rules.Decision) -> None:
        """Покупка боевых умений за очки полей."""
        from . import pages

        params = decision.params
        prefer = [pages.cyr_normalize(str(p)) for p in params.get("prefer", [])]
        max_price = int(params.get("max_price", 0) or 0)
        min_price = int(params.get("min_price", 0) or 0)
        try:
            self.game.goto("https://barbars.ru/trade/ability")
            ids = sorted(set(re.findall(r"trade/ability/buy/0/(\d+)", self.game.p.content())))
        except Exception as exc:
            self.log(f"умения: магазин не открылся: {exc}", "WARN")
            return
        if not ids:
            self.log("умения: список умений пуст")
            return
        bought = False
        for ability_id in ids:
            try:
                data = self.game.ability_options(ability_id)
            except Exception as exc:
                self.log(f"умения: не удалось получить варианты: {exc}", "WARN")
                continue
            points = int(data.get("points", 0) or 0)
            options = [o for o in data.get("options", []) if int(o.get("price", 0)) > 0]
            affordable = [
                o
                for o in options
                if int(o.get("price", 0)) <= points
                and int(o.get("price", 0)) <= max_price
                and int(o.get("price", 0)) >= min_price
            ]
            if not affordable:
                continue
            # приоритет: из списка желаемых — лучшее качество; затем самое дорогое
            def rank(opt: dict[str, Any]) -> tuple[int, int]:
                name = str(opt.get("name", ""))
                wanted = 0
                for i, want in enumerate(prefer):
                    if want and want in name:
                        wanted = len(prefer) - i
                        break
                quality = {
                    "мифический": 5,
                    "легендарный": 4,
                    "эпический": 3,
                    "редкий": 2,
                    "необычный": 1,
                    "обычный": 0,
                }.get(str(opt.get("quality", "")), 0)
                return (wanted, quality, int(opt.get("price", 0)))

            best = max(affordable, key=rank)
            if self.game.buy_ability_with_points(ability_id, int(best.get("index", 0))):
                bought = True
                self.log(
                    f"умения: куплено «{best.get('name')}» ({best.get('quality')}) "
                    f"за {best.get('price')} очков полей (было {points})"
                )
                break
        if not bought:
            self.log("умения: подходящих вариантов за очки полей нет")

    def _check_raid(self, state: rules.GameState) -> None:
        """Зал кланового босса: открыт ли вход, сколько HP у босса, кто в зале."""
        cfg = self.config.get("raid", {}) or {}
        if not cfg.get("enabled"):
            return
        now = time.time()
        if (now - self.raid_checked_at) < float(cfg.get("check_interval_min", 5)) * 60:
            state.raid = self.raid_cache
            return
        self.raid_checked_at = now
        try:
            info = self.game.raid_room(str(cfg.get("url", "https://barbars.ru/game/dragonDungeon")))
        except Exception as exc:
            self.log(f"рейд: не удалось проверить зал: {exc}", "WARN")
            state.raid = self.raid_cache
            return
        self.raid_cache = info
        state.raid = info
        ready = len(info.get("ready") or [])
        waiting = len(info.get("waiting") or [])
        self.log(
            "рейд: "
            + (
                f"вход закрыт, откроется через {info.get('reopen_in')}"
                if info.get("closed")
                else f"пещера открыта, HP босса {info.get('hp')}%"
            )
            + f", в зале {ready + waiting} (готовых {ready})"
            + (" — в попытку не пустили" if info.get("locked_out") else "")
        )

    def _do_raid(self, decision: rules.Decision, state: rules.GameState) -> None:
        """Рейд на кланового босса: собраться в зале, начать общий бой, бить.

        Механика игры: зал общий на 10 героев. Кто нажал «Начать бой!» — тот
        стартовал попытку, но в бой попадают все, кто стоял в зале готовым.
        Во время попытки страница зала отдаёт участнику боевую панель
        («Бить дракона» / «Лечить союзников»), поэтому достаточно перезагрузить
        зал — отдельного входа не нужно.
        """
        url = str(decision.params.get("url", "https://barbars.ru/game/dragonDungeon"))
        min_party = int(decision.params.get("min_party", 2))
        stay_sec = int(decision.params.get("stay_sec", 600))
        can_start = bool(decision.params.get("can_start", True))
        check_sec = int(decision.params.get("room_check_sec", 8))
        # заходим в зал не каждый цикл, а раз в repeat_min
        self.raid_last_at = time.time()
        self.daily["raid_last_at"] = self.raid_last_at
        self._save_daily()

        # уже в бою — просто бьём
        if "Покинуть бой" in self.game.body_text():
            self._raid_fight()
            return

        deadline = time.time() + stay_sec
        closed_checks = 0
        self.in_long_op = True  # сторож цикла не должен рвать браузер в рейде
        try:
            while time.time() < deadline:
                info = self.game.raid_room(url)
                if info.get("in_fight"):
                    # во время попытки зал отдаёт участнику боевую панель
                    self.log("рейд: мы в бою с боссом")
                    self._raid_fight()
                    # после боя ждём отката и пробуем снова — цикл «откат → убили»
                    continue
                if info.get("closed"):
                    # идёт попытка (или откат): зал нам боевую панель не отдал
                    closed_checks += 1
                    if closed_checks % 4 == 1 and self.game.join_current_fight(url):
                        self.log("рейд: вошли в общий бой")
                        self._raid_fight()
                        continue
                    time.sleep(check_sec)
                    continue
                closed_checks = 0
                ready = len(info.get("ready") or [])
                waiting = len(info.get("waiting") or [])
                self.log(f"рейд: в зале {ready + waiting} (готовых {ready})")
                # держим свою готовность: она сбрасывается, когда кто-то заходит
                self.game.raid_ready()
                if can_start and ready >= min_party and info.get("can_start"):
                    if self.game.raid_start():
                        self.log("рейд: начали общий бой с боссом")
                        time.sleep(2)
                        if "Покинуть бой" not in self.game.body_text():
                            self.game.join_current_fight(url)
                        self._raid_fight()
                        continue
                time.sleep(check_sec)
        finally:
            self.in_long_op = False
        self.log("рейд: окно вышло, ждём следующего")

    def _raid_fight(self) -> None:
        """Бой с боссом: воин бьёт, медик лечит.

        Лимит ходов тут свой: попытка длится около пяти минут, а обычного
        лимита боёв (40 ходов в облаке) не хватает — воин успевал сделать
        только 40 ударов и выходил из боя, не дожидаясь конца попытки.
        """
        limit = int(self.config.get("raid", {}).get("max_turns", 70))
        outcome = self._fight_loop(force=True, max_turns=limit)
        self.fights_done += 1
        self._bump("raid")
        self.log(
            f"рейд: бой с боссом завершён — {outcome}, нанесли урона {self.last_damage}"
        )
        self.game.click_text("Покинуть бой")

    def _do_scrolls(self, decision: rules.Decision, state: rules.GameState) -> None:
        """Активируем свитки (бесплатно при премиуме) и читаем книги."""
        params = decision.params
        only_free = bool(params.get("only_free", True))
        limit = int(params.get("limit", 5))
        done = 0
        for item in state.scrolls[:limit]:
            item_id = str(item.get("item_id", ""))
            name = str(item.get("name", ""))
            if not item_id:
                continue
            ok, message = self.game.activate_scroll(item_id, only_free=only_free)
            if ok:
                done += 1
                self.log(f"свитки: «{name}» — {message}")
            else:
                self.log(f"свитки: «{name}» — {message}")
        if done:
            self.log(f"свитки: активировано {done}")

    def _do_shop(self, decision: rules.Decision, state: rules.GameState) -> None:
        """Закупка снаряжения 25+ уровня в «Магазине снаряжения».

        Алгоритм по требованию игрока: выбираем вещи с максимальными
        характеристиками («Лучше (+N)») по каждому слоту, не дороже лимита
        по золоту; цену проверяем на странице товара (покупать вслепую нельзя);
        купленное приходит на почту — забираем и надеваем.
        """
        from . import pages

        max_gold = int(decision.params.get("max_gold", 3))
        max_silver = int(decision.params.get("max_silver", 0))
        sets = list(decision.params.get("sets", ["", "goliaf", "atlant", "veteran"]))
        max_buys = int(decision.params.get("max_buys", 2))
        min_bonus = int(decision.params.get("min_bonus", 10))
        avoid_same_name = bool(decision.params.get("avoid_same_name", True))
        min_level = int(self.config.get("shop", {}).get("min_level", 25))
        bought_slots = list(self.daily.get("shop_slots", []) or [])
        bought_today = set(self.daily.get("shop_buy_ids", []) or [])
        try:
            items: list[dict[str, Any]] = []
            for set_name in sets:
                items += self.game.shop_gear(set_name)
            worn = self.game.worn_gear()
        except Exception as exc:
            self.log(f"магазин: не удалось получить товары: {exc}", "WARN")
            return
        picked = pages.pick_shop_items(
            items,
            worn,
            max_gold,
            max_silver,
            bought_slots,
            # если вещи предназначены другому герою — берём лучшее по слоту
            # (у нас самих может быть всё уже лучше), без фильтра «дубль»
            require_better=not bool(self.config.get("shop", {}).get("share_with")),
            min_bonus=min_bonus,
            avoid_same_name=avoid_same_name,
            min_level=min_level,
        )
        picked = [i for i in picked if str(i.get("item_id", "")) not in bought_today]
        if not picked:
            self.log("магазин: подходящих товаров нет (лимит по золоту или нет денег)")
            return
        bought = 0
        bought_items: list[dict[str, Any]] = []
        for item in picked[:max_buys]:
            item_id = str(item.get("item_id", "") or "")
            name = str(item.get("name", ""))
            # цену смотрим на странице товара: там написано «Купить за …»
            try:
                gold_need, silver_need = self.game.shop_item_price(item_id)
            except Exception as exc:
                self.log(f"магазин: цену «{name}» узнать не удалось: {exc}", "WARN")
                continue
            if gold_need <= 0 and silver_need <= 0:
                self.log(f"магазин: «{name}» — цену не прочитали, пропускаем")
                continue
            if gold_need > max_gold:
                self.log(f"магазин: «{name}» — {gold_need} зол., лимит {max_gold}: пропускаем")
                continue
            if gold_need * 100 + silver_need > max_gold * 100:
                self.log(
                    f"магазин: «{name}» — {gold_need} зол. {silver_need} сер. "
                    f"(>{max_gold} зол. по лимиту): пропускаем"
                )
                continue
            if max_silver and silver_need > max_silver:
                continue
            have = int(state.gold or 0) * 100 + int(state.silver or 0)
            need = gold_need * 100 + silver_need
            if need + 100 > have:
                self.log(f"магазин: «{name}» не по карману (нужно {need} сер.)")
                continue
            ok, message = self.game.buy_shop_item_capped(item_id, max_gold)
            if not ok:
                self.log(f"магазин: «{name}» не куплена — {message}", "WARN")
                continue
            bought += 1
            bought_items.append(item)
            bought_today.add(item_id)
            slot, _kind = pages.slot_of(name)
            if slot and slot not in bought_slots:
                bought_slots.append(slot)
            self.log(f"магазин: куплена «{name}» ({item.get('level')} ур, +{item.get('bonus')}) — {message}")
        if not bought:
            return
        self.daily = self._load_daily()
        self.daily["shop_slots"] = bought_slots
        self.daily["shop_buy_ids"] = sorted(bought_today)
        bought_ids = list(self.daily.get("shop_bought", []) or [])
        for item in bought_items:
            item_id = str(item.get("item_id", "") or "")
            if item_id and item_id not in bought_ids:
                bought_ids.append(item_id)
        self.daily["shop_bought"] = bought_ids
        self._save_daily()
        # купленное приходит письмом — забираем и надеваем
        if self.game.take_mail():
            self.log("почта: купленное забрано")
        worn = self.game.equip_better_items(limit=int(self.config.get("gear", {}).get("max_equip", 8)))
        self.log(f"магазин: надето новых вещей {worn}")

        # передача купленного другому герою (например keis -> firewhite)
        share_with = str(self.config.get("shop", {}).get("share_with", "") or "")
        if share_with and bought_items:
            self._share_items(share_with, bought_items)

    def _do_auction(self, decision: rules.Decision, state: rules.GameState) -> None:
        """Дубли мифических вещей — на «Аукцион вещей» (или отправить тому,
        у кого аукцион доступен).

        Дубль — вещь, слот которой уже занят надетой. Мифические вещи не
        ломаем, поэтому лишние продаём лотом: начальная цена и цена выкупа.
        """
        params = decision.params
        max_per_cycle = int(params.get("max_per_cycle", 2))
        send_to = str(params.get("send_to", "") or "")
        bid_gold = int(params.get("bid_gold", 1))
        bid_silver = int(params.get("bid_silver", 0))
        buyout_gold = int(params.get("buyout_gold", 2))
        buyout_silver = int(params.get("buyout_silver", 0))
        done = 0
        for item in state.duplicates[:max_per_cycle]:
            name = str(item.get("name", "") or "")
            item_id = str(item.get("item_id", "") or "")
            if not name or not item_id:
                continue
            if send_to:
                if self.game.send_bag_item_to(send_to, item_id, f"{name} (дубль, на аукцион)"):
                    self.log(f"аукцион: «{name}» отправлена герою {send_to} на аукцион")
                    done += 1
                    self._bump("auction")
                else:
                    self.log(f"аукцион: «{name}» отправить не удалось", "WARN")
                continue
            ok, message = self.game.put_on_auction(
                item_id, bid_gold, bid_silver, buyout_gold, buyout_silver
            )
            if ok:
                self.log(f"аукцион: «{name}» выставлена — {message}")
                done += 1
                self._bump("auction")
            else:
                self.log(f"аукцион: «{name}» — {message}", "WARN")

    def _do_trade_market(self, decision: rules.Decision, state: rules.GameState) -> None:
        """Рынок аукционов вещей (/trade/auction): покупаем нужному герою.

        Лоты 25+ уровня мифического качества, не дороже лимита по золоту;
        если у нужного героя слот уже закрыт — берём другой лот (дубли не
        покупаем). Купленное уходит получателю почтой.
        """
        from . import pages

        params = decision.params
        max_gold = int(params.get("max_gold", 3))
        max_buys = int(params.get("max_buys", 1))
        min_level = int(params.get("min_level", 25))
        require_tier = str(params.get("require_tier", "мифический"))
        send_to = str(params.get("send_to", "") or "")
        try:
            lots = self.game.market_lots()
        except Exception as exc:
            self.log(f"рынок: не удалось получить лоты: {exc}", "WARN")
            return
        if not lots:
            self.log("рынок: лотов нет")
            return
        bought_today = set(self.daily.get("market_bought", []) or [])
        busy: dict[str, int] = {}
        for w in state.target_gear:
            slot, _kind = pages.slot_of(w.get("name", ""))
            if slot:
                busy[slot] = int(w.get("level", 0) or 0)
        bought = 0
        for lot in lots:
            if bought >= max_buys:
                break
            name = str(lot.get("name", "") or "")
            item_id = str(lot.get("item_id", "") or "")
            if not name or not item_id:
                continue
            if name in bought_today:
                continue
            if int(lot.get("level", 0)) < min_level:
                continue
            tier = str(lot.get("tier", ""))
            if require_tier and tier not in ("?", "") and tier != require_tier:
                continue
            slot, _kind = pages.slot_of(name)
            if slot and busy.get(slot, 0) >= int(lot.get("level", 0)):
                continue  # у героя слот уже закрыт — дубль не покупаем
            price = int(lot.get("price_silver", 0))
            if price > max_gold * 100:
                continue
            ok, message = self.game.buy_market_lot(item_id, int(lot.get("pt", 0)), max_gold)
            if not ok:
                self.log(f"рынок: «{name}» не куплена — {message}", "WARN")
                continue
            bought += 1
            bought_today.add(name)
            self._bump("market")
            self.log(f"рынок: куплена «{name}» ({lot.get('level')} ур, {tier or '?'}) — {message}")
            if send_to:
                if self.game.take_mail():
                    self.log("рынок: покупка забрана с почты")
                if self.game.send_bag_item_to(send_to, item_id, f"{name} (куплено на аукционе)"):
                    self.log(f"рынок: «{name}» отправлена герою {send_to}")
                else:
                    self.log(f"рынок: «{name}» отправить не удалось", "WARN")
        if bought:
            self.daily = self._load_daily()
            self.daily["market_bought"] = sorted(bought_today)
            self._save_daily()

    def _share_items(self, recipient_id: str, items: list[dict[str, Any]]) -> None:
        """Передать купленные вещи другому герою почтой (через витрину)."""
        try:
            # витрина должна содержать только передаваемые вещи
            self.game.store_take_all()
            for item in items:
                item_id = str(item.get("item_id", ""))
                if not item_id:
                    continue
                if not self.game.sell_item_to_store(item_id):
                    self.log(f"передача: не удалось выложить {item.get('name')}", "WARN")
                    return
            if self.game.send_store_items_to(recipient_id, "Снаряжение 25 уровня"):
                names = ", ".join(str(i.get("name", "")) for i in items)
                self.log(f"передача: отправлено получателю {recipient_id} — {names}")
            else:
                self.log("передача: отправить не удалось", "WARN")
        except Exception as exc:
            self.log(f"передача: ошибка — {exc}", "WARN")

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

    def _check_mail(self, state: rules.GameState) -> None:
        """Раз в 3 минуты смотрим почту: не прислали ли вещи."""
        if not self.config.get("mail", {}).get("enabled", True):
            return
        interval = float(self.config.get("mail", {}).get("check_interval_min", 3)) * 60
        now = time.time()
        if self.mail_checked_at and now - self.mail_checked_at < interval:
            state.mail_pending = self.mail_pending
            return
        try:
            self.mail_pending = self.game.mail_pending()
        except Exception as exc:
            self.log(f"почта: проверка не удалась: {exc}", "WARN")
            return
        self.mail_checked_at = now
        state.mail_pending = self.mail_pending
        if self.mail_pending:
            self.log("почта: есть что забрать")

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
        """Фарм-событие: зайти в активность и подраться, если противник появился.

        Чтобы герой не застревал в одном режиме, после `farm.max_streak` боёв
        подряд событие уходит на паузу (retry_min) — так очередь доходит до
        башен и других обязательных активностей.
        """
        name = decision.target or "событие"
        url = decision.params.get("url", "")
        wait_sec = int(decision.params.get("wait_sec", 120))
        retry = float(self.config.get("farm", {}).get("retry_min", 30))
        max_streak = int(self.config.get("farm", {}).get("max_streak", 3))
        # каждая попытка события считается: после N попыток — башня (фон)
        self.activity_fights += 1
        result = self.game.enter_activity(url, wait_sec=wait_sec)
        if not result.get("ok"):
            note = result.get("note") or result.get("stage") or "недоступно"
            self.farm_cooldown[name] = time.time() + retry * 60
            self.farm_streak[name] = 0
            self.log(f"событие «{name}» недоступно: {note} (пропустим {retry} мин)", "INFO")
            self.game.click_text("Покинуть бой")
            self._maybe_tower()
            return
        outcome = self._fight_loop()
        self.fights_done += 1
        self.farm_cooldown.pop(name, None)
        streak = self.farm_streak.get(name, 0) + 1
        self.farm_streak[name] = streak
        self.log(f"событие «{name}»: бой завершён — {outcome} ({streak}/{max_streak})")
        self.game.click_text("Покинуть бой")
        if max_streak and streak >= max_streak:
            self.farm_cooldown[name] = time.time() + retry * 60
            self.farm_streak[name] = 0
            self.log(f"событие «{name}»: пауза {retry} мин, идём к следующему")
        self._maybe_tower()

    def _maybe_tower(self) -> None:
        """Башня — постоянный фон: между событиями обязательно идём на неё."""
        tower_every = int(self.config.get("farm", {}).get("tower_every", 0) or 0)
        if not tower_every or self.activity_fights % tower_every:
            return
        rounds = int(self.config.get("tower_farm", {}).get("rounds", 3))
        self.log("чередуем: башня между событиями")
        self._do_tower(rules.Decision("tower", params={"rounds": rounds}))

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

    def _fight_loop(self, force: bool = False, max_turns: int = 0) -> str:
        """Пошаговый бой. `force` — режим босса: не ждём энергию перед лечением
        и считаем нанесённый по боссу урон. `max_turns` — свой лимит ходов."""
        turns = 0
        limit = max_turns or int(self.config.get("fight", {}).get("max_turns", 80))
        last_log = ""
        stale_energy_checks = 0
        stalls = 0
        last_energy = None
        damage = 0
        seen_logs: set[str] = set()
        target_hp: int | None = None

        def done(text: str) -> str:
            """Выход из боя: запоминаем, сколько урона нанесли."""
            self.last_damage = damage
            return text

        while turns < limit:
            if self.deadline and time.time() >= self.deadline:
                self.log("  выходим по лимиту времени")
                return done("время вышло")
            cs = self.game.combat()
            if cs.log_lines:
                new_log = cs.log_lines[-1]
                if new_log != last_log:
                    self.log(f"  ход {turns}: {new_log}")
                    last_log = new_log
                # урон по боссу считаем по журналу боя: «Ты ударил дракона на 209»
                for line in cs.log_lines:
                    if line in seen_logs:
                        continue
                    seen_logs.add(line)
                    m = re.search(r"дракона\s+на\s+(\d+)", line)
                    if m:
                        damage += int(m.group(1))
            if cs.victory is not None:
                return done("победа" if cs.victory else "поражение")
            if force and cs.enemy_hp and cs.enemy_hp != target_hp:
                # в шапке боевой панели — HP цели: следим за изменением
                target_hp = cs.enemy_hp
                self.log(f"  HP цели: {target_hp}")
            if cs.finished and not cs.attack_links:
                self.log("  бой окончен")
                return done("окончен")
            status = self.game.status()
            base = self.last_state or rules.GameState()
            state = rules.GameState(
                max_hp=base.max_hp or cs.our_hp or status.hp,
                max_energy=base.max_energy or cs.our_energy or status.energy,
            )
            decision = self.policy.choose(cs, status, state, force=force)
            if decision.action != "wait":
                stalls = 0
            self.game.human.pause("fight")
            if decision.action == "attack":
                turns += 1
                if not self.game.click_attack():
                    self.log("  не удалось ударить")
                    return done("прервано")
            elif decision.action == "ability":
                turns += 1
                used = self.game.use_ability(decision.params.get("href", ""))
                if used:
                    self.log(f"  умение: {decision.target}")
                else:
                    # умение не сработало (например, ОК пересоздал кадр) —
                    # бьём обычным ударом, чтобы бой не завис
                    self.log("  умение не применилось — бьём обычным ударом")
                    self.game.click_attack()
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
                return done("отступление")
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
                        return done("прервано")
            else:
                # В бою нет ни удара, ни умения (например, незнакомая вёрстка):
                # ждать бесконечно нельзя — иначе агент встанет на этом бою.
                stalls += 1
                if stalls >= 8:
                    self.log("  в бою нет доступных действий — выходим")
                    return done("нет действий")
                self.log("  нет доступных действий в бою — ждём")
                time.sleep(2)
        return done("таймаут")

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
