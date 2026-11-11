"""Оффлайн-тесты торговли: парсеры аукциона, колодца, мудреца и правила продажи.

Используют реальные HTML-дампы из knowledge/discovered (если их нет — тест пропускается).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from barbars import pages, rules  # noqa: E402

DISCOVERED = ROOT / "knowledge" / "discovered"


def load(name: str) -> str | None:
    path = DISCOVERED / f"{name}.html"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


class TestBazaarLots(unittest.TestCase):
    def test_bottle_lots(self) -> None:
        html = load("bazaar-bottles")
        if html is None:
            self.skipTest("нет дампа bazaar-bottles")
        lots = pages.parse_lots(html, "bottles")
        self.assertTrue(lots, "не разобраны лоты бутылочек")
        self.assertTrue(all(lot["amount"] > 0 for lot in lots))
        # в разметке лот 100 бутылок за 2 золота 50 серебра
        first = lots[0]
        self.assertEqual(first["amount"], 100)
        self.assertEqual(first["gold"], 2)
        self.assertEqual(first["silver"], 50)
        self.assertEqual(first["price_silver"], 250)

    def test_mifril_lots(self) -> None:
        html = load("bazaar-mifril")
        if html is None:
            self.skipTest("нет дампа bazaar-mifril")
        lots = pages.parse_lots(html, "mifril")
        self.assertTrue(lots)
        self.assertEqual(lots[0]["amount"], 2600)
        # медианная цена за единицу: ~8 серебра за мифрил (100 мфр за 8 зол? нет —
        # 2600 мфр за 200 зол = 7.69 сер/шт, 100 мфр за 7з90с = 7.9 сер/шт)
        median = pages.median_unit_price(lots)
        self.assertGreater(median, 7.0)
        self.assertLess(median, 9.0)
        # максимум — это явно завышенный лот (55 мфр за 4 зол 55 с)
        self.assertGreater(pages.best_unit_price(lots), median)

    def test_iron_not_in_bottle_lots(self) -> None:
        html = load("bazaar-bottles")
        if html is None:
            self.skipTest("нет дампа bazaar-bottles")
        self.assertEqual(pages.parse_lots(html, "iron"), [])


class TestWell(unittest.TestCase):
    def test_well_state(self) -> None:
        html = load("well")
        if html is None:
            self.skipTest("нет дампа well")
        info = pages.parse_well(html)
        self.assertTrue(info["gift_available"])
        self.assertTrue(info["book_available"])
        self.assertEqual(info["book_iron"], 10000)


class TestIronmaster(unittest.TestCase):
    def test_options(self) -> None:
        html = load("ironmaster")
        if html is None:
            self.skipTest("нет дампа ironmaster")
        options = pages.parse_ironmaster(html)
        self.assertEqual(len(options), 4)
        iron = [o for o in options if o["currency"] == "iron"]
        self.assertEqual([o["amount"] for o in iron], [10000, 5000])
        self.assertEqual([o["percent"] for o in iron], [5.0, 2.0])
        gold = [o for o in options if o["currency"] == "gold"]
        self.assertEqual(len(gold), 2)


class TestAutocrack(unittest.TestCase):
    def test_kinds(self) -> None:
        html = load("autocrack")
        if html is None:
            self.skipTest("нет дампа autocrack")
        kinds = [o["kind"] for o in pages.parse_autocrack(html)]
        self.assertIn("autoCrackCommonLink", kinds)
        self.assertIn("autoCrackOffLink", kinds)


class TestSaleRule(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def _state(self, **kwargs) -> rules.GameState:
        state = rules.GameState()
        state.mifril = kwargs.get("mifril", 0)
        state.bottles = kwargs.get("bottles", 0)
        state.market_prices = kwargs.get("prices", {})
        state.sold_today = kwargs.get("sold_today", 0)
        return state

    def test_no_sale_below_threshold(self) -> None:
        state = self._state(mifril=100, prices={"mifril": 8.0})
        self.assertIsNone(rules._pick_sale(state, self.config))

    def test_sale_when_enough(self) -> None:
        state = self._state(mifril=3000, prices={"mifril": 8.0})
        decision = rules._pick_sale(state, self.config)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "sell")
        self.assertEqual(decision.target, "mifril")
        reserve = int(self.config["market"]["reserve"]["mifril"])
        self.assertEqual(decision.params["amount"], 3000 - reserve)
        # цена = медиана рынка (8.0 сер/шт) без скидки
        self.assertEqual(decision.params["gold"], 236)
        self.assertEqual(decision.params["silver"], 0)

    def test_respect_reserve(self) -> None:
        state = self._state(bottles=320, prices={"bottles": 2.5})
        self.assertIsNone(rules._pick_sale(state, self.config))

    def test_daily_limit(self) -> None:
        limit = int(self.config["market"]["max_lots_per_day"])
        state = self._state(mifril=3000, prices={"mifril": 8.0}, sold_today=limit)
        self.assertIsNone(rules._pick_sale(state, self.config))

    def test_iron_never_sold(self) -> None:
        state = self._state(iron=999999, prices={"iron": 100.0})
        self.assertIsNone(rules._pick_sale(state, self.config))

    def test_no_second_lot_while_one_active(self) -> None:
        state = self._state(mifril=3000, prices={"mifril": 8.0})
        state.my_lots = [{"resource": "mifril", "amount": 500, "unit_price_silver": 8.0}]
        self.assertIsNone(rules._pick_sale(state, self.config))

    def test_cancel_lot_when_market_fell(self) -> None:
        state = self._state(prices={"mifril": 5.0})
        state.my_lots = [{"resource": "mifril", "amount": 500, "unit_price_silver": 8.0}]
        decision = rules._pick_cancel(state, self.config)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "cancel_lot")
        self.assertEqual(decision.target, "mifril")

    def test_keep_lot_if_price_fair(self) -> None:
        state = self._state(prices={"mifril": 8.0})
        state.my_lots = [{"resource": "mifril", "amount": 500, "unit_price_silver": 8.0}]
        self.assertIsNone(rules._pick_cancel(state, self.config))


class TestExpRule(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def test_exp_uses_iron_only(self) -> None:
        state = rules.GameState()
        state.iron = 500000
        state.exp_options = [
            {"percent": 5.0, "currency": "iron", "amount": 10000},
            {"percent": 2.0, "currency": "iron", "amount": 5000},
            {"percent": 27.0, "currency": "gold", "amount": 1350},
        ]
        decision = rules.decide(state, self.config)
        # без боёв и талантов выбирается покупка опыта за железо, а не за золото
        self.assertEqual(decision.action, "exp")
        self.assertEqual(decision.params["amount"], 10000)

    def test_exp_skipped_without_free_iron(self) -> None:
        state = rules.GameState()
        state.iron = 50000
        state.exp_options = [{"percent": 5.0, "currency": "iron", "amount": 10000}]
        decision = rules.decide(state, self.config)
        self.assertNotEqual(decision.action, "exp")

    def test_exp_limit_per_day(self) -> None:
        state = rules.GameState()
        state.iron = 500000
        state.exp_options = [{"percent": 5.0, "currency": "iron", "amount": 10000}]
        state.exp_buys_today = 1
        decision = rules.decide(state, self.config)
        self.assertNotEqual(decision.action, "exp")


class TestAltarRule(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def _state(self, **kwargs) -> rules.GameState:
        state = rules.GameState()
        state.iron = kwargs.get("iron", 500_000)
        state.silver = kwargs.get("silver", 0)
        state.gold = kwargs.get("gold", 27)
        state.altar_bonus = kwargs.get("bonus", 0.0)
        state.altar_expires_in_min = kwargs.get("ttl", 10)
        state.altar_options = kwargs.get("options", [])
        return state

    def test_silver_never_chosen(self) -> None:
        """По решению игрока алтарь продлевается только железом."""
        state = self._state(
            silver=200,
            options=[
                {"kind": "iron", "cost": 1250, "bonus": 12.5},
                {"kind": "silver", "cost": 87, "bonus": 25.0},
            ],
        )
        decision = rules.decide(state, self.config)
        self.assertEqual(decision.action, "altar")
        self.assertEqual(decision.target, "iron")

    def test_iron_when_silver_short(self) -> None:
        state = self._state(
            silver=50,
            options=[
                {"kind": "iron", "cost": 1250, "bonus": 12.5},
                {"kind": "silver", "cost": 87, "bonus": 25.0},
            ],
        )
        decision = rules.decide(state, self.config)
        self.assertEqual(decision.action, "altar")
        self.assertEqual(decision.target, "iron")

    def test_gold_option_never_chosen(self) -> None:
        state = self._state(
            silver=500,
            options=[
                {"kind": "iron", "cost": 1250, "bonus": 12.5},
                {"kind": "gold", "cost": 958, "bonus": 40.0},
            ],
        )
        decision = rules.decide(state, self.config)
        # золотой вариант запрещён — выбираем железный
        self.assertEqual(decision.action, "altar")
        self.assertEqual(decision.target, "iron")

    def test_silver_respects_keep_reserve(self) -> None:
        state = self._state(
            silver=90,  # 87 + 20 = 107 нужно, чтобы оставить резерв
            options=[{"kind": "silver", "cost": 87, "bonus": 25.0}],
        )
        decision = rules.decide(state, self.config)
        self.assertNotEqual(decision.action, "altar")

    def test_waits_for_bonus_to_expire(self) -> None:
        """Текущий бонус 25% (серебряный) — железом его не понижаем, ждём протухания."""
        state = self._state(
            bonus=25.0,
            ttl=10,  # почти протух, но ещё жив
            options=[{"kind": "iron", "cost": 1250, "bonus": 12.5}],
        )
        decision = rules.decide(state, self.config)
        self.assertNotEqual(decision.action, "altar")

    def test_renews_same_bonus_level(self) -> None:
        """Бонус 12,5% и почти протух — продлеваем тем же железом, без простоя."""
        state = self._state(
            bonus=12.5,
            ttl=10,
            options=[{"kind": "iron", "cost": 1250, "bonus": 12.5}],
        )
        decision = rules.decide(state, self.config)
        self.assertEqual(decision.action, "altar")
        self.assertEqual(decision.target, "iron")


class TestFarmRule(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def test_first_event_chosen(self) -> None:
        state = rules.GameState()
        decision = rules._pick_farm(state, self.config)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.action, "activity")
        self.assertTrue(decision.params["url"].startswith("https://barbars.ru/"))

    def test_skip_blocked_event(self) -> None:
        state = rules.GameState()
        state.farm_skip = [self.config["farm"]["events"][0]["name"]]
        decision = rules._pick_farm(state, self.config)
        self.assertIsNotNone(decision)
        self.assertNotEqual(decision.target, state.farm_skip[0])

    def test_all_skipped_returns_none(self) -> None:
        state = rules.GameState()
        state.farm_skip = [e["name"] for e in self.config["farm"]["events"]]
        self.assertIsNone(rules._pick_farm(state, self.config))


if __name__ == "__main__":
    unittest.main(verbosity=2)
