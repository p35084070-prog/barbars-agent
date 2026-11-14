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


def dragon_panel(pct="73%", warriors=2, medics=1, events=(), extra=""):
    # Minimal structure retained from the project's captured real raid pages.
    icons = f'<div><img src="/images/icons/dragon_mif.png"><span>{pct}</span>'
    icons += f'<img src="/images/icons/blue_warrior.png"><span>{warriors}</span>'
    icons += f'<img src="/images/icons/blue_healer.png"><span>{medics}</span>'
    icons += '<img src="/images/icons/clock.png"><span>08:17</span></div>'
    return icons + ''.join(f'<div><img src="/images/icons/clock2.png">{e}</div>' for e in events) + extra


def test_dragon_percent_uses_dragon_icon_not_hero_hp():
    from barbars.raid_evidence import parse_dragon_evidence
    e = parse_dragon_evidence('<img src="life.png"><span>8084</span><span>25%</span>' + dragon_panel())
    assert e['boss_hp_pct'] == 73
    assert e['warriors_alive'] == 2 and e['medics_alive'] == 1
    assert e['combat_clock'] == '08:17'


@pytest.mark.parametrize('extra', ['<div>Ты погиб</div>', '<div>Поражение</div>', '<form><div>Дракон повержен</div></form>', '<div class="guildChat"><div>Победа</div></div>'])
def test_personal_death_and_chat_are_not_team_loss_or_win(extra):
    from barbars.raid_evidence import parse_dragon_evidence
    assert parse_dragon_evidence(dragon_panel(extra=extra))['terminal'] is None


@pytest.mark.parametrize('label,outcome', [('Дракон повержен', 'победа'), ('Ваш отряд погиб', 'поражение')])
def test_team_result_above_long_footer(label, outcome):
    from barbars.raid_evidence import parse_dragon_evidence
    e = parse_dragon_evidence(dragon_panel(extra=f'<h2>{label}</h2>') + '<footer>' + '<div>Ссылка</div>' * 30 + '</footer>')
    assert e['terminal'] == outcome


def test_zero_percent_rounding_is_not_victory():
    from barbars.raid_evidence import parse_dragon_evidence
    assert parse_dragon_evidence(dragon_panel(pct='0%'))['terminal'] is None


def test_all_dead_with_explicit_defeat():
    from barbars.raid_evidence import parse_dragon_evidence
    assert parse_dragon_evidence(dragon_panel(warriors=0, medics=0, extra='<h2>Поражение</h2>'))['terminal'] == 'поражение'


def test_all_dead_but_dragon_alive_confirms_team_loss():
    from barbars.raid_evidence import parse_dragon_evidence
    e = parse_dragon_evidence(dragon_panel(pct='23%', warriors=0, medics=0, events=['Ты погиб']))
    assert e['terminal'] == 'поражение'
    assert e['boss_hp_pct'] == 23


def test_empty_waiting_roster_is_not_a_loss():
    from barbars.raid_evidence import parse_dragon_evidence
    assert parse_dragon_evidence(dragon_panel(warriors=0, medics=0))['terminal'] is None


def test_event_overlap_keeps_repeated_hits_and_restart_without_double_count():
    from barbars.raid_evidence import parse_dragon_evidence, record_sample
    a = 'Ты ударил дракона на 357'
    b = 'Ты ударил дракона на 500 крит'
    active = {}
    record_sample(active, parse_dragon_evidence(dragon_panel(events=[a, b])), 1)
    active = json.loads(json.dumps(active))
    record_sample(active, parse_dragon_evidence(dragon_panel(events=[b, a])), 2)
    assert active['damage_lower_bound'] == 1214
    record_sample(active, parse_dragon_evidence(dragon_panel(events=[b, a])), 3)
    assert active['damage_lower_bound'] == 1214
    assert active['event_totals_exact'] is False


def test_heal_requests_are_not_actual_healing(tmp_path):
    from barbars.raid_evidence import parse_dragon_evidence, record_sample
    active = {'healing_requests': 49}
    record_sample(active, parse_dragon_evidence(dragon_panel(events=['Ты начал бой'])), 1)
    assert active.get('healing_lower_bound', 0) == 0
    record_sample(active, parse_dragon_evidence(dragon_panel(events=['Ты вылечил союзника на 280'])), 2)
    assert active['healing_lower_bound'] == 280


def test_raid_turn_limit_is_unconfirmed_and_preserved(tmp_path):
    a = agent(tmp_path)
    a.runtime['raid_active'] = {'started_at': 1}
    a.game.combat.return_value = CombatState(attack_links=['Бить дракона'], our_hp=100, our_energy=100)
    a.game.status.return_value = Status(hp=100, energy=100)
    with patch('barbars.loop.time.sleep'):
        assert a._fight_loop(force=True, max_turns=1) == 'лимит ходов'
    a._fight_loop = Mock(return_value='лимит ходов')
    a._raid_fight()
    assert a.runtime['raid_active']
    a.game.click_text.assert_not_called()


def test_evidence_persists_progress_and_separates_units(tmp_path):
    from barbars.raid_evidence import parse_dragon_evidence
    a = agent(tmp_path)
    a.runtime['raid_active'] = {'started_at': 1}
    a._record_raid_evidence(CombatState(raid_evidence=parse_dragon_evidence(dragon_panel(pct='19%'))))
    recovered = agent(tmp_path).runtime['raid_active']
    assert recovered['boss_last_hp_pct'] == 19
    assert recovered['latest_evidence']['warriors_alive'] == 2


def test_clan_counter_increase_is_not_blindly_attributed_to_our_party(tmp_path):
    a = agent(tmp_path)
    a.runtime['raid_active'] = {'started_at': 1, 'clan_kills_before': 7}
    a.game.raid_clan_kills.return_value = 8
    a._finish_raid('результат не подтверждён')
    assert a.runtime['last_raid']['clan_kill_confirmed'] is True
    assert a.runtime['last_raid']['outcome'] == 'результат не подтверждён'


def test_peer_cooldown_recovers_missed_closed_period_after_restart(tmp_path):
    from barbars.safety import SpawnWitness
    peer = SpawnWitness(tmp_path, 'ok', ['keis'])
    peer.publish(1100, 1200)
    leader = SpawnWitness(tmp_path, 'keis', ['ok'])
    assert leader.reopened_since(1000, 1300)['account'] == 'ok'
    assert leader.reopened_since(1000, 1199) is None
    assert leader.reopened_since(1250, 1300) is None
    assert leader.reopened_since(0, 1300) is None


def test_saved_old_server_countdown_migrates_but_not_local_clock(tmp_path):
    from barbars.safety import SpawnWitness, atomic_json
    leader = SpawnWitness(tmp_path, 'keis', ['ok'])
    atomic_json(tmp_path / 'state/ok/runtime.json', {'raid_reopen_at': 1200})
    assert leader.reopened_since(1000, 1300)['source'] == 'persisted server cooldown'
    atomic_json(tmp_path / 'state/ok/runtime.json', {'raid_next_check_at': 1200})
    assert leader.reopened_since(1000, 1300) is None


def test_peer_unlock_still_requires_full_party_and_live_dragon(tmp_path):
    a = respawn_agent(tmp_path)
    a.runtime.update(raid_wait_for_closed=True, last_raid={'started_at': 1000})
    a.spawn_witness.reopened_since = Mock(return_value={'account': 'ok', 'reopen_at': 1200})
    a.game.raid_room.side_effect = [open_dragon(), open_dragon(), open_dragon()]
    a._raid_fight = Mock()
    a._do_respawn_raid()
    a.game.raid_start.assert_called_once()
    assert not a.runtime['raid_wait_for_closed']


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
    cfg["raid"]["every_respawn"] = False
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
    g.page = SimpleNamespace(title=lambda: "Мифический дракон", locator=locator,
                             content=lambda: dragon_panel(events=['Ты вылечил союзников на 200']))
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


@pytest.mark.parametrize("name", CONFIGS)
def test_real_cloud_config_paths(name):
    from run import load_config
    cfg = load_config(ROOT / name)
    assert Path(cfg["_root"]) == ROOT
    assert (Path(cfg["_root"]) / cfg["daily_file"]).relative_to(ROOT).parts[0] == "state"
    assert (Path(cfg["_root"]) / cfg["state_dir"]).relative_to(ROOT).parts[0] == "logs"
    credentials = cfg.get("auth", {}).get("credentials_file")
    if credentials:
        assert (Path(cfg["_root"]) / credentials).relative_to(ROOT).parts[0] == "credentials"


@pytest.mark.parametrize("raw,expected", [("00:05:20", 320), ("01:02:03", 3723), ("05:20", 320), ("", None), ("unknown", None), ("00:99:20", None)])
def test_server_respawn_timer(raw, expected):
    from barbars.safety import respawn_seconds
    assert respawn_seconds(raw) == expected


def respawn_agent(tmp_path, name=CONFIGS[0]):
    a = agent(tmp_path, name)
    a.config["raid"]["every_respawn"] = True
    return a


def open_dragon():
    info = room()
    info["hp"] = 100
    return info


def test_respawn_mode_ignores_half_hour_windows(tmp_path):
    a = respawn_agent(tmp_path)
    a._do_respawn_raid = Mock()
    with patch("barbars.loop.time.time", return_value=18900), patch("barbars.loop.rules.collect_state") as collect:
        assert a._run_once_inner().action == "raid"
    a._do_respawn_raid.assert_called_once()
    collect.assert_not_called()


@pytest.mark.parametrize("name,starts", [(CONFIGS[0], True), (CONFIGS[1], False), (CONFIGS[2], False)])
def test_every_respawn_has_only_one_leader(tmp_path, name, starts):
    a = respawn_agent(tmp_path, name)
    a.game.raid_room.side_effect = [open_dragon(), open_dragon()] + ([open_dragon()] if starts else []) + [{"valid": True, "closed": True, "reopen_in": "00:10:00"}]
    a._raid_fight = Mock()
    with patch("barbars.loop.time.time", return_value=18900), patch("barbars.loop.time.sleep"):
        a._do_respawn_raid()
    assert a.game.raid_start.called == starts


def test_cooldown_gives_time_for_farming_and_reserves_pre_spawn(tmp_path):
    a = respawn_agent(tmp_path)
    with patch("barbars.loop.time.time", return_value=1000):
        a._schedule_respawn_check({"reopen_in": "00:20:00"})
        assert a.runtime["raid_next_check_at"] == 1300
        assert a.runtime["raid_guard_until"] == 1000
        a._schedule_respawn_check({"reopen_in": "00:02:00"})
        assert a.runtime["raid_next_check_at"] == 1005
        assert a.runtime["raid_guard_until"] == 1150
    with patch("barbars.loop.time.time", return_value=1001), patch("barbars.loop.rules.collect_state") as collect:
        decision = a._run_once_inner()
    assert decision.action == "wait" and decision.params["sleep_sec"] == 5
    collect.assert_not_called()


def test_same_spawn_is_not_started_twice_after_restart(tmp_path):
    a = respawn_agent(tmp_path)
    a.runtime["raid_wait_for_closed"] = True
    a._save_runtime()
    a = respawn_agent(tmp_path)
    a.game.raid_room.return_value = open_dragon()
    a._do_respawn_raid()
    a.game.raid_start.assert_not_called()
    a.game.raid_room.return_value = {"valid": True, "closed": True, "reopen_in": "00:02:00"}
    a._do_respawn_raid()
    assert not a.runtime["raid_wait_for_closed"]
    a.game.raid_room.side_effect = [open_dragon(), open_dragon(), open_dragon()]
    a._raid_fight = Mock()
    a._do_respawn_raid()
    a.game.raid_start.assert_called_once()


@pytest.mark.parametrize("hp", [0, None])
def test_dead_or_unknown_dragon_never_starts(tmp_path, hp):
    a = respawn_agent(tmp_path)
    info = open_dragon()
    info["hp"] = hp
    a.game.raid_room.return_value = info
    a._do_respawn_raid()
    a.game.raid_start.assert_not_called()
    a.game.raid_ready.assert_not_called()


def test_unknown_respawn_page_denies_ready_and_start(tmp_path):
    a = respawn_agent(tmp_path)
    a.game.raid_room.return_value = {"valid": False}
    a._do_respawn_raid()
    a.game.raid_ready.assert_not_called()
    a.game.raid_start.assert_not_called()


def test_respawn_mode_restores_active_battle(tmp_path):
    a = respawn_agent(tmp_path)
    a.runtime["raid_active"] = {"started_at": 1, "observed_combat": True}
    a._save_runtime()
    a = respawn_agent(tmp_path)
    a.game.raid_room.return_value = {"valid": True, "in_fight": True}
    a._raid_fight = Mock()
    a._do_respawn_raid()
    a._raid_fight.assert_called_once()
    a.game.raid_start.assert_not_called()


@pytest.mark.parametrize("name", CONFIGS)
def test_all_live_configs_use_respawn_mode(name):
    cfg = config(name)
    assert cfg["raid"]["every_respawn"]
    assert cfg["raid"]["max_fights_per_day"] == 0
