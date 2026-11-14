"""Explicit offline suite. Never collect or execute the live probe scripts."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from barbars import pages, rules
from barbars.driver import CombatState, Game, Status
from barbars.loop import Agent
from barbars.safety import RepairBudget, party_ready, raid_window

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ["deploy/config-actions-keis.json", "deploy/config-actions-firewhite.json", "config-ok.json"]


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    def forbidden(*args, **kwargs):
        raise AssertionError("offline test attempted a network request")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)


def config(name=CONFIGS[0]):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def agent(tmp_path, name=CONFIGS[0]):
    cfg = config(name)
    cfg["_root"] = str(tmp_path)
    game = Mock()
    game.body_text.return_value = ""
    game.combat.return_value = CombatState()
    return Agent(game, cfg, tmp_path / "logs")


def room(ids=("905853", "31389504", "1286381"), ready=True):
    names = {"905853": "keis", "31389504": "firewhite", "1286381": "vagojan"}
    rows = "".join(f'<div><a href="../user/id/{i};jsessionid=REMOVED"><span>{names.get(i, "stranger")}</span></a>'
                   + ('<img src="/images/icons/check_green.png">' if ready else "")
                   + ('<img src="blue_healer.png">' if i == "905853" else '<img src="blue_warrior.png">') + "</div>" for i in ids)
    return pages.parse_raid_room('Мифический дракон Кто здесь [3 из 10]' + rows + '<a href="?startCombatLink">Начать бой!</a>')


@pytest.mark.parametrize("name", CONFIGS)
def test_cloud_policies(name):
    c = config(name)
    assert c["raid"]["min_party"] == 3
    assert c["raid"]["can_start"] == (c["account"] == "keis")
    assert c["raid"]["leader"] == "keis"
    assert {p["id"] for p in c["raid"]["party"]} == {"905853", "31389504", "1286381"}
    assert c["gear"]["keep_mythic"] and not c["gear"]["sell_store"] and not c["gear"]["auto_equip"]
    assert c["scrolls"]["mode"] == "discard"
    assert c["spend"]["buy_iron"]["max_gold"] == 1
    assert not c["exp"]["buy_with_gold"] and not c["spend"]["allow_gold_fights"]
    assert c["fight"]["prefer_heal"] == (c["account"] == "keis")


@pytest.mark.parametrize("ids,allowed", [
    (("905853", "31389504", "1286381"), True),
    (("905853", "31389504"), False),
    (("31389504", "1286381", "999"), False),
    (("905853", "31389504", "999"), False),
    (("905853", "905853", "1286381"), False),
])
def test_exact_party(ids, allowed):
    assert party_ready(room(ids), config()["raid"]) is allowed


def test_not_ready_and_unknown():
    assert not party_ready(room(ready=False), config()["raid"])
    assert not pages.parse_raid_room("Вход для игроков")["valid"]
    info = pages.parse_raid_room("Вход закрыт. Другой герой начал бой. Ты не можешь принять участие. Покинуть бой")
    assert not info["in_fight"] and info["locked_out"]
    assert pages.parse_raid_room('<a href="?healRandomFriendLink">Лечить союзников</a>')["in_fight"]


def test_readiness_does_not_bleed_across_rows():
    h = 'Кто здесь<div><a href="user/id/1"><span>one</span></a></div><div><a href="user/id/2"><span>two</span></a><img src="check_green.png"></div>'
    info = pages.parse_raid_room(h)
    assert [p["id"] for p in info["ready"]] == ["2"]
    assert [p["id"] for p in info["waiting"]] == ["1"]


def test_shared_windows():
    for name in CONFIGS:
        assert raid_window(config(name)["raid"], 18000) == (10, 18600, True)
        assert raid_window(config(name)["raid"], 18601)[2] is False


@pytest.mark.parametrize("fatigue", [None, -1, -15, -36, 1])
def test_all_tower_paths_deny_fatigue(tmp_path, fatigue):
    a = agent(tmp_path)
    a.game.hero_fatigue.return_value = fatigue
    assert rules._pick_tower(rules.GameState(tire=fatigue), a.config) is None
    a._do_tower(rules.Decision("tower"))
    a.activity_fights = 3
    a._maybe_tower()
    a._do_fight(rules.Decision("fight", target="Башня", params={"href": "game/towers"}))
    a.game.open_tower.assert_not_called()
    a.game.goto.assert_not_called()
    # Pause survives a process restart.
    assert agent(tmp_path).runtime["tower_paused"]


def test_tower_resumes_only_at_zero(tmp_path):
    a = agent(tmp_path)
    a.runtime["tower_paused"] = True
    a.game.hero_fatigue.return_value = 0
    a.game.open_tower.return_value = None
    a._do_tower(rules.Decision("tower"))
    a.game.open_tower.assert_called_once()
    assert not a.runtime["tower_paused"]


@pytest.mark.parametrize("text,expected", [("усталость: -1%", -1), ("усталость: 0%", 0), ("нет усталости", 0), ("Вход для игроков", None), ("Мой герой", None)])
def test_fatigue_parser(text, expected):
    g = Game({}, ".")
    g.goto = Mock()
    g.body_text = Mock(return_value=text)
    assert g.hero_fatigue() == expected


def test_medic_heals_before_damage_or_energy_wait():
    policy = rules.CombatPolicy(config())
    cs = CombatState(heal_links=["Лечить союзников"], attack_links=["Жечь"], our_energy=0,
                     abilities=[{"ready": True, "desc": "увеличивает урон", "name": "boost", "href": "x"}])
    assert policy.choose(cs, Status(), rules.GameState(max_energy=5000), force=True).action == "heal"


def test_budget_restart_daily_bound_and_unknown(tmp_path):
    path = tmp_path / "budget.json"
    b = RepairBudget(path, "keis")
    reserved = b.reserve()
    assert reserved and RepairBudget(path, "keis").reserve() is None
    b.finish(reserved, {"ok": True, "gold": 1, "silver": 0, "qty": 100})
    assert RepairBudget(path, "keis").reserve() is None
    data = json.loads(path.read_text())
    data.update(date="2000-01-01", status="pending")
    path.write_text(json.dumps(data))
    assert RepairBudget(path, "keis").reserve() is None


def test_corrupt_budget_and_failed_remote_save_deny_spending(tmp_path):
    p = tmp_path / "budget.json"
    p.write_text("broken")
    with pytest.raises(ValueError):
        RepairBudget(p, "keis").reserve()
    b = RepairBudget(tmp_path / "remote.json", "keis")
    b._save = Mock(side_effect=RuntimeError("CAS conflict"))
    with pytest.raises(RuntimeError):
        b.reserve()


def test_emergency_repairs_only():
    c = config()
    for iron, repair, cost in [(None, True, 10), (1, True, 10), (0, False, 10), (0, True, None)]:
        assert rules._pick_buy_iron(rules.GameState(iron=iron, needs_repair=repair, repair_cost=cost, gold=50), c) is None
    d = rules._pick_buy_iron(rules.GameState(iron=0, needs_repair=True, repair_cost=7, gold=50), c)
    assert d.params["max_gold"] == 1 and d.params["min_iron"] == 7


def test_no_equipment_changes_or_mythic_destruction():
    g = Game({}, ".")
    g.goto = Mock()
    assert g.equip_better_items() == 0
    g.goto.assert_not_called()
    g.page = Mock()
    g.page.content.return_value = '<span class="bonusdarkiron">Мифический меч</span><a href="crackIronPanel:crackLink">Разобрать</a>'
    g.click_href = Mock()
    assert not g._crack_item_page("1")
    assert not g.sell_item_to_store("1")
    assert not g.crack_all_items()
    g.click_href.assert_not_called()


def test_scrolls_discard_only(tmp_path):
    a = agent(tmp_path)
    a._do_scrolls(rules.Decision("scrolls", params={"limit": 5}), rules.GameState(scrolls=[
        {"item_id": "1", "name": "Свиток силы"}, {"item_id": "2", "name": "Манускрипт"}]))
    a.game.discard_scroll.assert_called_once_with("1")
    a.game.activate_scroll.assert_not_called()


@pytest.mark.parametrize("outcome", ["таймаут", "нет действий", "прервано", "время вышло"])
def test_unfinished_raid_is_not_left_or_counted(tmp_path, outcome):
    a = agent(tmp_path)
    a.runtime["raid_active"] = {"window": 10, "started_at": 18001}
    a._fight_loop = Mock(return_value=outcome)
    a._raid_fight()
    assert a.runtime["raid_active"]
    assert a.daily.get("raid", 0) == 0
    a.game.click_text.assert_not_called()


def test_confirmed_result_counted_once(tmp_path):
    a = agent(tmp_path)
    a.runtime["raid_active"] = {"window": 10, "started_at": 18001}
    a._fight_loop = Mock(return_value="победа")
    a._raid_fight()
    a._finish_raid("победа")
    assert a.daily["raid"] == 1
    assert agent(tmp_path).runtime["last_raid"]["outcome"] == "победа"


@pytest.mark.parametrize("name,starts", [(CONFIGS[0], True), (CONFIGS[1], False), (CONFIGS[2], False)])
def test_only_leader_starts_with_actual_party(tmp_path, name, starts):
    a = agent(tmp_path, name)
    info = room()
    a.game.raid_room.side_effect = [info, info, {"valid": True, "closed": True, "locked_out": True}]
    a._raid_fight = Mock()
    with patch("barbars.loop.time.time", return_value=18001), patch("barbars.loop.time.sleep"):
        a._do_raid(rules.Decision("raid"), rules.GameState())
    assert a.game.raid_start.called == starts


def test_incomplete_party_never_starts(tmp_path):
    a = agent(tmp_path)
    info = room(("31389504", "1286381", "999"))
    a.game.raid_room.side_effect = [info, info, {"valid": True, "closed": True, "locked_out": True}]
    with patch("barbars.loop.time.time", return_value=18001), patch("barbars.loop.time.sleep"):
        a._do_raid(rules.Decision("raid"), rules.GameState())
    a.game.raid_start.assert_not_called()


def test_active_raid_resumed_before_farming(tmp_path):
    a = agent(tmp_path)
    a.runtime["raid_active"] = {"window": 10, "started_at": 18001}
    a.game.raid_room.return_value = {"in_fight": True, "valid": True}
    a._raid_fight = Mock()
    with patch("barbars.loop.rules.collect_state") as collect:
        a._run_once_inner()
    a._raid_fight.assert_called_once()
    collect.assert_not_called()


def test_real_row_icon_before_link():
    info = pages.parse_raid_room('Кто здесь<div><img src="check_green.png"><span><img src="blue_healer.png"><a href="../user/id/905853"><span>keis</span></a></span></div>')
    assert info["ready"] == [{"id": "905853", "name": "keis", "role": "medic"}]


def test_wrong_or_unknown_class_denies_start():
    info = room()
    info["ready"][0]["role"] = "warrior"
    assert not party_ready(info, config()["raid"])


def test_medic_parser_does_not_finish_while_heal_button_exists():
    g = Game({}, ".")
    link = Mock()
    link.inner_text.return_value = "Лечить союзников"
    link.get_attribute.return_value = "?actionPanel:healRandomFriendLink"
    def locator(selector):
        return SimpleNamespace(all=lambda: [link] if selector == "a" else [])
    g.page = SimpleNamespace(title=lambda: "Мифический дракон", locator=locator)
    g.status = Mock(return_value=Status(hp=400, energy=0))
    g.body_text = Mock(return_value="Ты вылечил союзников на 200\nЛечить союзников\nПокинуть бой")
    cs = g.combat()
    assert cs.heal_links == ["Лечить союзников"]
    assert not cs.finished


@pytest.mark.parametrize("confirmed", [True, False])
def test_purchase_requires_verified_wallet_and_resource_changes(confirmed):
    g = Game({}, ".")
    g.goto = Mock()
    g._settle = Mock()
    g.page = Mock()
    g.page.content.return_value = '<div>100 жлз <img src="money_gold.png"><span>1</span></div>'
    g.body_text = Mock(return_value="Да, подтверждаю")
    g.click_text = Mock(return_value=True)
    g.iron_lots = Mock(return_value=[{"qty": 100, "gold": 1, "silver": 0, "href": "offer"}])
    g.status = Mock(side_effect=[Status(iron=0, gold=3, silver=50),
                                Status(iron=100 if confirmed else 0, gold=2, silver=50)])
    result = g.buy_iron_with_gold(7, 40)
    assert result["ok"] is confirmed
    assert result["gold"] == 1
    assert not result["not_submitted"]


def test_ambiguous_confirmation_never_submits():
    g = Game({}, ".")
    g.goto = Mock()
    g.page = Mock()
    g.page.content.return_value = '<div>100 жлз по цене 50</div>'
    g.body_text = Mock(return_value="Да, подтверждаю")
    g.click_text = Mock()
    g.iron_lots = Mock(return_value=[{"qty": 100, "gold": 1, "silver": 0, "href": "offer"}])
    g.status = Mock(return_value=Status(iron=0, gold=3, silver=50))
    assert g.buy_iron_with_gold(7, 1)["not_submitted"]
    g.click_text.assert_not_called()


def test_fifty_silver_is_not_converted_to_gold():
    g = Game({}, ".")
    g.goto = Mock()
    g._settle = Mock()
    g.page = Mock()
    g.page.content.return_value = '<div>100 жлз <img src="money_silver.png"><span>50</span></div>'
    g.body_text = Mock(return_value="Да, подтверждаю")
    g.click_text = Mock(return_value=True)
    g.iron_lots = Mock(return_value=[{"qty": 100, "gold": 0, "silver": 50, "href": "offer"}])
    g.status = Mock(side_effect=[Status(iron=0, gold=0, silver=50), Status(iron=100, gold=0, silver=0)])
    result = g.buy_iron_with_gold(7, 1)
    assert result["ok"] and result["gold"] == 0 and result["silver"] == 50


def test_remote_budget_uses_sha_and_never_retries_a_conflict(tmp_path):
    import base64
    b = RepairBudget(tmp_path / "budget.json", "keis")
    b.remote = True
    b._request = Mock(side_effect=[
        {"sha": "previous-sha", "content": base64.b64encode(b'{}').decode()},
        RuntimeError("CAS conflict"),
    ])
    with pytest.raises(RuntimeError):
        b.reserve()
    assert b._request.call_args_list[-1].args[0] == "PUT"
    assert b._request.call_args_list[-1].args[1]["sha"] == "previous-sha"
    assert b._request.call_count == 2


def test_budget_denial_does_not_starve_farming(tmp_path):
    a = agent(tmp_path)
    a.last_state = rules.GameState(iron=0, needs_repair=True, repair_cost=7)
    a.repair_budget.reserve = Mock(return_value=None)
    a._do_buy_iron(rules.Decision("buy_iron"))
    a.game.buy_iron_with_gold.assert_not_called()
    assert not a._gated_config(0)["spend"]["buy_iron"]["enabled"]


def test_unknown_start_is_not_counted_as_a_completed_attempt(tmp_path):
    a = agent(tmp_path)
    a.runtime["raid_active"] = {"window": 10, "started_at": 18001}
    a._finish_raid("результат не подтверждён")
    assert a.daily.get("raid", 0) == 0


def test_unreadable_price_is_not_free():
    g = Game({}, ".")
    link = Mock()
    link.evaluate.side_effect = RuntimeError("detached frame")
    assert g._near_paid(link)


def test_repair_refuses_currency_payment():
    g = Game({}, ".")
    g.page = Mock()
    g.page.locator.return_value.count.return_value = 1
    g._near_paid = Mock(return_value=True)
    assert not g.repair_all()
    g.page.locator.return_value.first.click.assert_not_called()
