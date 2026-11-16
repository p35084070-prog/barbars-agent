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
CONFIGS = ["deploy/config-actions-keis.json", "deploy/config-actions-firewhite.json", "config-ok.json", "config-ok2.json"]


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


def test_missing_fourth_hero_cannot_be_replaced_by_a_stranger():
    cfg = config()['raid']
    assert not party_ready(room(('905853', '31389504', '1286381', '999')), cfg)
    assert not party_ready(room(('31389504', '1286381', '1596900', '999')), cfg)


def test_ok2_has_isolated_cloud_state_and_session():
    first, second = config(CONFIGS[2]), config(CONFIGS[3])
    assert second['account'] == 'ok2'
    for key in ('profile_dir', 'state_dir', 'daily_file'):
        assert first[key] != second[key]
    assert second['ok_channel']['session_env'] == 'OK2_SESSION_B64'
    assert second['ok_channel']['session_file'] != first['ok_channel']['session_file']
    workflow = (ROOT / '.github/workflows/agent-ok2.yml').read_text(encoding='utf8')
    assert '${{ secrets.OK2_LOGIN }}' in workflow and '${{ secrets.OK2_PASSWORD }}' in workflow
    assert 'group: agent-ok2' in workflow and 'agent-ok2.yml/dispatches' in workflow
    assert 'python -m pytest tests/test_safety_offline.py -q' in workflow
    assert 'state/ok2/daily.json' in workflow and 'state/ok2/runtime.json' in workflow
    assert '${{ secrets.OK_SESSION_B64 }}' not in workflow


@pytest.mark.parametrize('hero_id,klass,guild,valid', [('1596900','воин',16675,True), ('1286381','воин',16675,False),
                                                    ('1596900','медик',16675,False), ('1596900','воин',1,False)])
def test_new_account_identity_guard(hero_id, klass, guild, valid):
    from run import verify_expected_hero
    from barbars.driver import GameError
    game = Mock(hero_id=hero_id)
    game.hero.return_value = SimpleNamespace(klass=klass, guild_id=guild)
    if valid:
        verify_expected_hero(game, config(CONFIGS[3])['expected_hero'])
    else:
        with pytest.raises(GameError):
            verify_expected_hero(game, config(CONFIGS[3])['expected_hero'])


def test_only_mithril_in_real_keis_mail_form_denies_iron_without_submit():
    game = Game({}, '.')
    game.goto = Mock()
    game.click_href = Mock(return_value=True)
    option = Mock()
    option.inner_text.return_value = 'Мифрил'
    option.get_attribute.side_effect = lambda key: '3' if key == 'value' else None
    game.page = Mock()
    game.page.locator.return_value.all.return_value = [option]
    result = game.send_resources_to('31389504', 'iron', 10000)
    assert result['ok'] is False and 'недоступна' in result['message']
    game.page.select_option.assert_not_called()
    game.page.click.assert_not_called()


def test_ok_compromised_profile_notice_is_a_protection_barrier():
    from tools.ok_auto_login import challenge_on_page
    page = Mock()
    page.inner_text.return_value = 'Мы заметили, что этот профиль мог попасть к злоумышленникам. Необходимо проверить данные.'
    assert challenge_on_page(page) == 'попасть к злоумышленникам'


def test_ok_login_prefers_exact_button_and_verifies_filled_values():
    from tools.ok_auto_login import do_login
    page = Mock()
    def locator(selector):
        value = 'test-login' if 'st.email' in selector else 'test-password'
        return SimpleNamespace(first=SimpleNamespace(input_value=lambda: value))
    page.locator.side_effect = locator
    assert do_login(page, 'test-login', 'test-password') == ''
    page.get_by_role.assert_called_once_with('button', name='Войти', exact=True)
    page.get_by_role.return_value.click.assert_called_once()


def test_ok_login_denies_submission_when_reactive_form_erases_login():
    from tools.ok_auto_login import do_login
    page = Mock()
    page.locator.return_value.first.input_value.return_value = ''
    assert 'запрещена' in do_login(page, 'test-login', 'test-password')
    page.get_by_role.assert_not_called()


def test_real_no_warriors_end_panel_confirms_failed_raid():
    from barbars.raid_evidence import parse_dragon_evidence
    e = parse_dragon_evidence('<div>Лечить некого</div><div>Все воины убиты</div><div>fire white ii погиб от удара дракона</div>')
    assert e['terminal'] == 'поражение'
    assert e['boss_hp_pct'] is None


def test_result_log_starts_with_outcome_and_fits_live_ui(tmp_path):
    a = agent(tmp_path)
    a.log = Mock()
    a.runtime['raid_active'] = {'started_at': 1, 'party': config()['raid']['party'], 'samples': [{'notices': ['x' * 100]}] * 120,
                              'boss_last_hp_pct': 66, 'latest_evidence': {'terminal_evidence': ['Все воины убиты']}}
    a._finish_raid('поражение')
    message = a.log.call_args.args[0]
    assert '"outcome": "поражение"' in message
    assert len(message) < 1000
    assert a.runtime['last_raid']['boss_hp_pct'] == 66


def test_raid_keeps_initial_energy_ceiling_before_first_state_collection(tmp_path):
    a = agent(tmp_path, CONFIGS[1])
    a.runtime['raid_active'] = {'started_at': 1}
    a.game.combat.side_effect = [CombatState(attack_links=['Бить дракона'], our_hp=100, our_energy=1000),
                               CombatState(attack_links=['Бить дракона'], our_hp=100, our_energy=100),
                               CombatState(victory=True)]
    a.game.status.return_value = Status(hp=100, energy=100)
    with patch('barbars.loop.time.sleep'):
        assert a._fight_loop(force=True, max_turns=5) == 'победа'
    a.game.click_attack.assert_called_once()
    a.game.reload.assert_called_once()
    assert a.runtime['raid_active']['energy_ceiling'] == 1000


def test_saved_maximum_survives_partial_charge_at_restart(tmp_path):
    a = agent(tmp_path, CONFIGS[1])
    a.runtime.update(hero_maxima={'max_energy': 3000}, raid_active={'started_at': 1})
    a._save_runtime()
    a = agent(tmp_path, CONFIGS[1])
    a.game.combat.side_effect = [CombatState(attack_links=['Бить дракона'], our_hp=100, our_energy=700), CombatState(victory=True)]
    a.game.status.return_value = Status(hp=100, energy=700)
    with patch('barbars.loop.time.sleep'):
        a._fight_loop(force=True, max_turns=5)
    a.game.click_attack.assert_not_called()
    a.game.reload.assert_called_once()


def test_live_combat_rows_without_clock2_and_actual_polechil_word():
    from barbars.raid_evidence import parse_dragon_evidence, record_sample
    e = parse_dragon_evidence(dragon_panel(extra='<div>Ты ударил дракона на 357</div><div>keis полечил тебя на 2518</div><div>Ты полечил себя на 3296 крит</div>'))
    active = {}
    record_sample(active, e, 1)
    assert active['damage_lower_bound'] == 357
    assert active['healing_lower_bound'] == 3296
    assert active['healing_received_lower_bound'] == 2518


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


PARTY_IDS = ("905853", "31389504", "1286381", "1596900", "11604269")


def room(ids=PARTY_IDS, ready=True):
    names = {"905853": "keis", "31389504": "firewhite", "1286381": "vagojan",
             "1596900": "qdal", "11604269": "Pandei"}
    rows = "".join(f'<div><a href="../user/id/{i};jsessionid=REMOVED"><span>{names.get(i, "stranger")}</span></a>'
                   + ('<img src="/images/icons/check_green.png">' if ready else "")
                   + ('<img src="blue_healer.png">' if i == "905853" else '<img src="blue_warrior.png">') + "</div>" for i in ids)
    return pages.parse_raid_room('Мифический дракон Кто здесь [3 из 10]' + rows + '<a href="?startCombatLink">Начать бой!</a>')


@pytest.mark.parametrize("name", CONFIGS)
def test_cloud_policies(name):
    c = config(name)
    assert c["raid"]["min_party"] == 5
    assert c["raid"]["can_start"] == (c["account"] == "keis")
    assert c["raid"]["leader"] == "keis"
    assert {p["id"] for p in c["raid"]["party"]} == set(PARTY_IDS)
    assert sum(1 for p in c["raid"]["party"] if p.get("role") == "medic") == 1
    assert c["gear"]["keep_mythic"] and not c["gear"]["sell_store"] and not c["gear"]["auto_equip"]
    assert c["scrolls"]["mode"] == "discard"
    assert c["spend"]["buy_iron"]["max_gold"] == 1
    assert not c["exp"]["buy_with_gold"] and not c["spend"]["allow_gold_fights"]
    assert c["fight"]["prefer_heal"] == (c["account"] == "keis")


@pytest.mark.parametrize("ids,allowed", [
    (PARTY_IDS, True),
    (("905853", "31389504", "1286381", "1596900"), False),
    (("905853", "31389504", "1286381"), False),
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


@pytest.mark.parametrize("name,starts", [(CONFIGS[0], True), (CONFIGS[1], False), (CONFIGS[2], False), (CONFIGS[3], False)])
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
    # Рейд на паузе в живых конфигах, но алгоритм проверяем с включённым рейдом.
    a.config["raid"]["enabled"] = True
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
    # Рейд в пещеру дракона стоит на паузу (см. knowledge/AUTONOMY_SAFETY.md),
    # но алгоритм рейда должен остаться рабочим — тесты включают его явно.
    a.config["raid"]["every_respawn"] = True
    a.config["raid"]["enabled"] = True
    return a


def open_dragon():
    info = room()
    info["hp"] = 100
    return info


def test_open_dragon_after_long_wait_unblocks_the_party(tmp_path):
    # Пещера открыта и предлагает бой дольше отката — значит прошлая попытка
    # не началась. Ожидание «подтверждённого возрождения» не должно блокировать
    # отряд навсегда.
    a = respawn_agent(tmp_path)
    a.config["raid"]["stuck_grace_sec"] = 600
    a.runtime.update(raid_wait_for_closed=True, raid_wait_for_closed_since=1000,
                     last_raid={"started_at": 900, "party": []})
    a.game.raid_room.side_effect = ([open_dragon()] * 8
                                    + [{"valid": True, "closed": True, "reopen_in": "00:10:00"}])
    a._raid_fight = Mock()
    with patch("barbars.loop.time.time", return_value=1601), patch("barbars.loop.time.sleep"):
        a._do_respawn_raid()
    assert a.runtime["raid_wait_for_closed"] is False
    assert a.game.raid_ready.called


def test_fresh_wait_for_closed_keeps_guarding(tmp_path):
    # Пока откат не прошёл, новую попытку не разрешаем.
    a = respawn_agent(tmp_path)
    a.config["raid"]["stuck_grace_sec"] = 600
    a.runtime.update(raid_wait_for_closed=True, raid_wait_for_closed_since=1500)
    a.game.raid_room.return_value = open_dragon()
    with patch("barbars.loop.time.time", return_value=1601), patch("barbars.loop.time.sleep"):
        a._do_respawn_raid()
    assert a.runtime["raid_wait_for_closed"] is True
    a.game.raid_ready.assert_not_called()


def test_assembly_gives_up_and_returns_to_farming(tmp_path):
    # Если полный отряд не собрался за assembly_max_sec, герой выходит из
    # зала: иначе протухшая сессия ОК блокирует ему весь день.
    a = respawn_agent(tmp_path)
    a.config["raid"]["assembly_sec"] = 0
    a.config["raid"]["assembly_max_sec"] = 600
    a.config["raid"]["assembly_return_sec"] = 300
    a.runtime["raid_assembly_since"] = 1000
    a.game.raid_room.return_value = open_dragon()
    a.game.click_text = Mock()
    with patch("barbars.loop.time.time", return_value=1700), patch("barbars.loop.time.sleep"):
        a._do_respawn_raid()
    assert a.runtime["raid_assembly_since"] == 0
    assert a.runtime["raid_next_check_at"] == 1700 + 300
    a.game.click_text.assert_called_with("Покинуть бой")


def test_goto_retries_once_after_timeout():
    # Короткий сетевой сбой не должен ронять весь сеанс агента.
    from playwright.sync_api import TimeoutError as PWTimeout

    g = Game({}, ".")
    g.page = Mock()
    g.page.goto.side_effect = [PWTimeout("boom"), None]
    g._settle = Mock()
    g.human.pause = Mock()
    g.human.maybe_scroll = Mock()
    g.goto("https://barbars.ru/")
    assert g.page.goto.call_count == 2


def test_goto_gives_up_after_second_timeout():
    from playwright.sync_api import TimeoutError as PWTimeout
    from barbars.driver import GameError

    g = Game({}, ".")
    g.page = Mock()
    g.page.goto.side_effect = [PWTimeout("boom"), PWTimeout("boom")]
    g._settle = Mock()
    g.human.pause = Mock()
    g.human.maybe_scroll = Mock()
    with pytest.raises(GameError):
        g.goto("https://barbars.ru/")
    assert g.page.goto.call_count == 2


def test_respawn_mode_ignores_half_hour_windows(tmp_path):
    a = respawn_agent(tmp_path)
    a._do_respawn_raid = Mock()
    with patch("barbars.loop.time.time", return_value=18900), patch("barbars.loop.rules.collect_state") as collect:
        assert a._run_once_inner().action == "raid"
    a._do_respawn_raid.assert_called_once()
    collect.assert_not_called()


@pytest.mark.parametrize("name,starts", [(CONFIGS[0], True), (CONFIGS[1], False), (CONFIGS[2], False), (CONFIGS[3], False)])
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
def test_live_configs_have_raid_armed_for_five(name):
    # Рейд на мифического дракона включён по решению игрока: ждём пещеру Pandei.
    cfg = config(name)
    assert cfg["raid"]["enabled"] is True
    assert cfg["raid"]["every_respawn"] is False
    assert cfg["raid"]["max_fights_per_day"] == 0
    assert cfg["raid"]["party"], "состав рейда должен остаться в конфиге"
    assert cfg["raid"]["min_party"] == 5
    assert len(cfg["raid"]["party"]) == 5


@pytest.mark.parametrize("icon,tier", [
    ("bonusdarkiron", "мифический"),
    ("bonuslegendary", "легендарный"),
    ("bonusepic", "эпический"),
    ("bonusrare", "редкий"),
    ("bonusgreen", "необычный"),
    ("bonuscopper", "обычный"),
])
def test_item_tier_from_bonus_icon(icon, tier):
    assert pages.item_tier(f'<div class="{icon}">вещь</div>') == tier


def _bag_html(tier_class: str) -> str:
    return ('<div class="hr"></div>'
            '<div><a href="../user/rack;jsessionid=X?items:0:crackIronPanel:crackLink">разобрать</a>'
            f'<a href="../item/id/123"><span>Меч Атланта</span></a><span class="{tier_class}"></span></div>')


@pytest.mark.parametrize("tier_class", ["bonusdarkiron", "bonuslegendary", "bonusepic"])
def test_dragon_reward_tiers_are_never_cracked(tier_class):
    # Награда за мифического дракона: 1 мифическая + 1 легендарная + 1 эпическая.
    g = Game({}, ".")
    g.page = Mock()
    g.page.content.return_value = _bag_html(tier_class)
    g.goto = Mock()
    g.click_href = Mock(return_value=True)
    assert g.crack_items(limit=3) == 0
    g.click_href.assert_not_called()


def test_junk_tiers_are_still_cracked():
    g = Game({}, ".")
    g.page = Mock()
    g.page.content.return_value = _bag_html("bonuscopper")
    g.goto = Mock()
    g.click_href = Mock(return_value=True)
    assert g.crack_items(limit=1) == 1
    g.click_href.assert_called_once()


@pytest.mark.parametrize("name", CONFIGS)
def test_gear_cleanup_protects_reward_tiers(name):
    # keep_tiers из конфига (по умолчанию) не должен пропускать наградные вещи.
    cfg = config(name)
    keep = tuple(cfg.get("gear", {}).get("keep_tiers", ("мифический", "легендарный", "эпический")))
    assert set(keep) == {"мифический", "легендарный", "эпический"}


# --- сторож усталости: строка есть только когда усталость есть -------------

def test_fatigue_line_absent_on_loaded_hero_page_means_no_fatigue():
    # Игра показывает «усталость: -N%» только когда усталость ЕСТЬ. Отсутствие
    # строки на открытой странице героя = усталости нет (0), а не «неизвестно».
    g = Game({}, ".")
    g.goto = Mock()
    g.body_text = Mock(return_value="Мой герой\n36 ур, воин, север\nСнаряжение (12)\nДостижения: 17")
    assert g.hero_fatigue() == 0


def test_fatigue_still_unknown_when_hero_page_did_not_load():
    g = Game({}, ".")
    g.goto = Mock()
    g.body_text = Mock(return_value="Вход для игроков")
    assert g.hero_fatigue() is None


def test_tower_farms_when_fatigue_reads_zero():
    a = agent(Path(ROOT))
    state = rules.GameState(tire=0)
    decision = rules._pick_tower(state, a.config)
    assert decision is not None and decision.action == "tower"


# --- Поля сражений: вступаем только у старта боя ----------------------------

def _bg_html():
    return ('<a href="game/bg?start=1">Игра начнётся через 00:47:33</a>'
            '<a href="game/bg?join=1">Вступить в бой</a>')


def test_countdown_link_is_not_a_join_link():
    info = pages.parse_battlefields(_bg_html(), "Игра начнётся через 00:47:33")
    assert len(info["join"]) == 1
    assert "Вступить" in info["join"][0]["label"]


def test_battlefields_decision_waits_for_start():
    cfg = {"battlefields": {"enabled": True, "join_lead_sec": 120}}
    far = pages.parse_battlefields(_bg_html(), "Игра начнётся через 00:47:33 Мои очки полей: 12 Сегодня боёв: 0")
    assert far["points"] == 12
    assert rules._pick_battlefields(rules.GameState(battlefields=far, bg_points=12), cfg) is None
    near = pages.parse_battlefields(_bg_html(), "Игра начнётся через 00:00:45 Мои очки полей: 12 Сегодня боёв: 0")
    decision = rules._pick_battlefields(rules.GameState(battlefields=near, bg_points=12), cfg)
    assert decision is not None and decision.action == "battlefields"


def test_battlefields_respects_daily_limit():
    cfg = {"battlefields": {"enabled": True, "join_lead_sec": 120, "max_fights_per_day": 5}}
    near = pages.parse_battlefields(_bg_html(), "Игра начнётся через 00:00:45 Мои очки полей: 12 Сегодня боёв: 5")
    assert rules._pick_battlefields(rules.GameState(battlefields=near, bg_points=12), cfg) is None


# --- вклад в клан выключен, алтарь только у keis ----------------------------

@pytest.mark.parametrize("name", CONFIGS)
def test_no_clan_storage_donation_anywhere(name):
    cfg = config(name)
    assert cfg.get("spend", {}).get("clan_donate", {}).get("enabled") is False


def test_only_keis_donates_to_the_altar():
    keis = config("deploy/config-actions-keis.json")
    assert keis["altar"]["enabled"] is True
    for name in CONFIGS:
        if name == "deploy/config-actions-keis.json":
            continue
        assert config(name)["altar"]["enabled"] is False

def test_altar_link_is_not_a_battlefields_join_link():
    # На странице полей есть ссылка «Зайти в алтарь» (это алтарь клана).
    # Раньше она считалась входом в бой — агент «вступал» не туда.
    html = ('<a href="../guild/altar;jsessionid=ABC">Зайти в алтарь</a>'
            '<a href="game/bg?join=1">Вступить в бой</a>')
    info = pages.parse_battlefields(html, "Игра начнётся через 00:00:30")
    assert [j["label"] for j in info["join"]] == ["Вступить в бой"]


def test_battlefields_decision_when_countdown_is_near_even_without_button():
    # Кнопка входа появляется только в момент старта: решаем идти по отсчёту.
    cfg = {"battlefields": {"enabled": True, "join_lead_sec": 300}}
    info = pages.parse_battlefields("<div>Игра начнётся через 00:02:10</div>", "Игра начнётся через 00:02:10 Мои очки полей: 5")
    assert info["join"] == []
    assert rules._pick_battlefields(rules.GameState(battlefields=info, bg_points=5), cfg) is not None


def test_battlefields_no_decision_when_far_and_no_button():
    cfg = {"battlefields": {"enabled": True, "join_lead_sec": 300}}
    info = pages.parse_battlefields("<div>Игра начнётся через 00:34:34</div>", "Игра начнётся через 00:34:34 Мои очки полей: 0")
    assert rules._pick_battlefields(rules.GameState(battlefields=info, bg_points=0), cfg) is None

def test_tower_attack_hits_enemies_before_the_tower_itself():
    # На странице локации башни две кнопки: «Бить башню» и «Бить врагов».
    # Бьём врагов — они дают опыт, железо и бутылочки.
    clicked = []

    class Link:
        def __init__(self, href, text):
            self.href = href
            self.text = text

        def scroll_into_view_if_needed(self, timeout=None):
            pass

        def click(self, timeout=None):
            clicked.append(self.href)

        def inner_text(self):
            return self.text

    class Loc:
        def __init__(self, links):
            self.links = links

        def count(self):
            return len(self.links)

        @property
        def first(self):
            return self.links[0]

        def all(self):
            return self.links

    tower = Link("?wicket:interface=:4:actionPanel:damageTowerLink::ILinkListener::", "Бить башню (11691 хп)")
    enemies = Link("?wicket:interface=:4:actionPanel:damageRandomEnemyLink::ILinkListener::", "Бить врагов")

    class Page:
        def locator(self, selector):
            if "damageRandomEnemyLink" in selector:
                return Loc([enemies])
            if "damageTowerLink" in selector:
                return Loc([tower])
            if "Бить" in selector:
                return Loc([tower, enemies])
            return Loc([])

    g = Game({}, ".")
    g.page = Page()
    g._settle = Mock()
    g.human = Mock()
    assert g.click_attack() is True
    assert "damageRandomEnemyLink" in clicked[0]


def test_tower_attack_retries_when_link_is_stale():
    # Wicket перерисовывает страницу: первый клик падает, второй по новой ссылке.
    clicked = []
    state = {"first": True}

    class Link:
        def __init__(self, href, stale=False):
            self.href = href
            self.stale = stale

        def scroll_into_view_if_needed(self, timeout=None):
            pass

        def click(self, timeout=None):
            if self.stale:
                state["first"] = False
                raise RuntimeError("element is not attached to the DOM")
            clicked.append(self.href)

        def inner_text(self):
            return "Бить врагов"

    class Loc:
        def __init__(self, link):
            self.link = link

        def count(self):
            return 1

        @property
        def first(self):
            return self.link

        def all(self):
            return [self.link]

    class Page:
        def locator(self, selector):
            if "damageRandomEnemyLink" in selector:
                return Loc(Link("?damageRandomEnemyLink::", stale=state["first"]))
            if "damageTowerLink" in selector:
                return Loc([])
            if "Бить" in selector:
                return Loc(Link("?damageRandomEnemyLink::", stale=state["first"]))
            return Loc([])

    g = Game({}, ".")
    g.page = Page()
    g._settle = Mock()
    g.human = Mock()
    g.reload = Mock()
    assert g.click_attack() is True
    assert clicked


def _shop_agent():
    """Агент с включённым магазином снаряжения (без реальной игры)."""
    cfg = json.loads(Path("deploy/config-actions-keis.json").read_text(encoding="utf-8"))
    cfg["shop"].update({"enabled": True, "max_gold": 1, "max_silver": 0})
    agent = Agent.__new__(Agent)
    agent.config = cfg
    agent.daily = {}
    agent.game = Mock()
    agent.log = Mock()
    agent._load_daily = Mock(return_value={})
    agent._save_daily = Mock()
    return agent


def test_shop_respects_daily_purchase_limit():
    """Дневной лимит покупок: не покупаем сверх max_buys_per_day."""
    agent = _shop_agent()
    agent.config["shop"]["max_buys_per_day"] = 2
    agent.daily = {"shop_buy_ids": ["a", "b"], "shop_slots": []}
    agent._do_shop(rules.Decision("shop", params={"max_gold": 1, "max_buys": 5}), rules.GameState(gold=50))
    agent.game.shop_gear.assert_not_called()


def test_shop_keeps_gold_reserve():
    """keep_gold: не опускаем золото ниже резерва."""
    agent = _shop_agent()
    agent.config["shop"]["keep_gold"] = 10
    item = {
        "item_id": "77", "name": "Шлем Воина", "level": 25, "bonus": 20,
        "gold": 1, "silver": 0, "price_ok": True, "tier": "mythic",
    }
    agent.game.shop_gear.return_value = [item]
    agent.game.worn_gear.return_value = []
    agent.game.shop_item_price.return_value = (1, 0)
    agent.game.buy_shop_item_capped.return_value = (True, "куплена")
    # золота 11: покупка за 1 оставит 10 — ровно резерва, можно
    agent._do_shop(rules.Decision("shop", params={"max_gold": 1, "max_buys": 1}), rules.GameState(gold=11))
    assert agent.game.buy_shop_item_capped.call_count == 1
    # золота 10: покупка опустит ниже резерва — нельзя
    agent.game.buy_shop_item_capped.reset_mock()
    agent._do_shop(rules.Decision("shop", params={"max_gold": 1, "max_buys": 1}), rules.GameState(gold=10))
    assert agent.game.buy_shop_item_capped.call_count == 0


def test_shop_for_other_hero_ignores_min_bonus_and_duplicate_names():
    """Покупаем для другого героя: «Лучше» и «дубль» надетого не важны."""
    agent = _shop_agent()
    agent.config["shop"]["share_with"] = "31390082"
    agent.config["shop"]["min_bonus"] = 10
    agent.config["shop"]["avoid_same_name"] = True
    item = {
        "item_id": "77", "name": "Шлем Воина", "level": 25, "bonus": 0,
        "gold": 1, "silver": 0, "price_ok": True, "tier": "mythic",
    }
    agent.game.shop_gear.return_value = [item]
    agent.game.worn_gear.return_value = [{"name": "Шлем Воина", "slot": "шлем"}]
    agent.game.shop_item_price.return_value = (1, 0)
    agent.game.buy_shop_item_capped.return_value = (True, "куплена")
    agent._do_shop(rules.Decision("shop", params={"max_gold": 1, "max_buys": 1}), rules.GameState(gold=50))
    assert agent.game.buy_shop_item_capped.call_count == 1


def test_auto_equip_requires_explicit_flag():
    """Экипировка по умолчанию выключена — только под флагом gear.auto_equip."""
    g = Game({"gear": {"auto_equip": False}}, ".")
    g.goto = Mock()
    g.page = Mock()
    assert g.equip_better_items() == 0
    g.goto.assert_not_called()


def test_steelblue_config_is_valid_and_keeps_gold_rules():
    """Конфиг пятого героя: золото не тратим, рейд и вклады выключены."""
    cfg = json.loads(Path("deploy/config-actions-steelblue.json").read_text(encoding="utf-8"))
    assert cfg["account"] == "steelblue"
    assert cfg["raid"]["enabled"] is False
    assert cfg["spend"]["clan_donate"]["enabled"] is False
    assert cfg["altar"]["enabled"] is False
    assert cfg["shop"]["enabled"] is False
    assert cfg["shop"]["max_gold"] == 1
    assert cfg["gear"]["auto_equip"] is True

def _shop_price_html(money: str) -> str:
    return (
        '<div class="border">'
        '<a href="?wicket:interface=:7:border:buyoutLink::ILinkListener::">'
        'Купить за ' + money + '</a></div>'
    )


def test_shop_price_html_reads_silver_only():
    """Цена «Купить за 55» с иконкой серебра — это 55 серебра."""
    html = _shop_price_html(
        '<img class="internalIcon" src="/images/icons/money_silver.png"><span>55</span>'
    )
    assert pages.parse_shop_price_html(html) == (0, 55)


def test_shop_price_html_reads_gold_and_silver_together():
    """«Купить за 6 30» = 6 золота 30 серебра, а не 6 серебра."""
    html = _shop_price_html(
        '<img class="internalIcon" src="/images/icons/money_gold.png"><span>6</span>'
        '<img class="internalIcon" src="/images/icons/money_silver.png"><span>30</span>'
    )
    assert pages.parse_shop_price_html(html) == (6, 30)


def test_shop_price_html_ignores_stat_icons():
    """Иконки характеристик после цены не должны попадать в цену."""
    html = _shop_price_html(
        '<img src="/images/icons/money_silver.png"><span>55</span>'
        '<img src="/images/icons/life.png"><span>350</span>'
        '<img src="/images/icons/shield.png"><span>290</span>'
    )
    assert pages.parse_shop_price_html(html) == (0, 55)


def test_buy_shop_item_capped_rejects_combined_price_over_limit():
    """Предмет дороже лимита (в пересчёте на серебро) не покупается."""
    g = Game({}, ".")
    g.goto = Mock()
    g.click_href = Mock(return_value=True)
    g.confirm_if_needed = Mock()
    g._settle = Mock()
    g.page = SimpleNamespace(content=lambda: _shop_price_html(
        '<img src="/images/icons/money_gold.png"><span>6</span>'
        '<img src="/images/icons/money_silver.png"><span>30</span>'
    ))
    ok, msg = g.buy_shop_item_capped("1", max_gold=1)
    assert ok is False
    assert "лимит" in msg
    g.click_href.assert_not_called()


def test_buy_shop_item_capped_allows_price_within_limit():
    """Предмет в пределах лимита покупается."""
    g = Game({}, ".")
    g.goto = Mock()
    g.click_href = Mock(return_value=True)
    g.confirm_if_needed = Mock()
    g._settle = Mock()
    g.page = SimpleNamespace(content=lambda: _shop_price_html(
        '<img src="/images/icons/money_silver.png"><span>55</span>'
    ))
    ok, msg = g.buy_shop_item_capped("1", max_gold=1)
    assert ok is True
    assert "55" in msg


# --- чистка сундука от хлама (16.11.2026) -----------------------------------
# Правила игрока: мифические/легендарные/эпические (награда за дракона) не
# трогаем никогда; «Лучше» — такую вещь надо надеть; обычный хлам разбираем
# на железо (crack) либо выбрасываем (drop).

CHEST_ITEM = (
    '<div class="hr"></div>'
    '<div><a href="../user/store;jsessionid=X?items:0:crackIronPanel:crackLink">разобрать</a>'
    '<a href="../item/id/123"><span>Куртка Дружинника</span></a>'
    '<span class="bonusrare"></span></div>'
)
CHEST_EMPTY = '<div class="hr"></div><div>Сундук пуст</div>'
ITEM_CRACK = '<a href="../?wicket:interface=:5:crackIronPanel:crackLink">разобрать на железо</a>'
ITEM_DROP = '<a href="../?wicket:interface=:5:crackIronPanel:dropLink">выкинуть</a>'


def _chest_game(pages_html):
    g = Game({}, ".")
    g.page = Mock()
    g.page.content.side_effect = pages_html
    g.goto = Mock()
    g.click_href = Mock(return_value=True)
    g.body_text = Mock(return_value="Куртка Дружинника 12 ур")
    return g


def test_protected_tier_in_chest_is_never_touched():
    g = _chest_game([CHEST_ITEM.replace("bonusrare", "bonusdarkiron")])
    res = g.clean_chest(limit=1, action="crack")
    assert res["cracked"] == 0 and res["dropped"] == 0
    g.click_href.assert_not_called()


def test_crack_mode_cracks_junk_for_iron():
    g = _chest_game([CHEST_ITEM, ITEM_CRACK, CHEST_EMPTY])
    res = g.clean_chest(limit=2, action="crack")
    assert res["cracked"] == 1 and res["dropped"] == 0
    g.click_href.assert_called_once_with("crackIronPanel:crackLink")


def test_crack_mode_falls_back_to_drop_when_item_gives_no_iron():
    g = _chest_game([CHEST_ITEM, ITEM_DROP, CHEST_EMPTY])
    res = g.clean_chest(limit=2, action="crack")
    assert res["dropped"] == 1 and res["cracked"] == 0
    g.click_href.assert_called_once_with("crackIronPanel:dropLink")


def test_drop_mode_never_cracks():
    # «Выкинуть» сжигает железо — в режиме drop разбор не делаем.
    g = _chest_game([CHEST_ITEM, ITEM_CRACK, CHEST_EMPTY])
    res = g.clean_chest(limit=2, action="drop")
    assert res["cracked"] == 0 and res["dropped"] == 0


def test_off_mode_does_nothing():
    g = _chest_game([CHEST_ITEM, ITEM_CRACK])
    res = g.clean_chest(limit=2, action="off")
    assert res == {"cracked": 0, "dropped": 0, "skipped": 0}
    g.click_href.assert_not_called()


CONFIRM_PAGE = "Подтверждение Подтверди, что хочешь разобрать эту вещь на железо Да, подтверждаю Нет, отмена"


def test_crack_waits_for_confirmation():
    # Без «Да, подтверждаю» вещь остаётся целой — разбор не засчитываем.
    g = _chest_game([CHEST_ITEM, ITEM_CRACK, CONFIRM_PAGE, CHEST_EMPTY])
    g.body_text = Mock(return_value=CONFIRM_PAGE)
    g.confirm_if_needed = Mock(return_value=False)
    res = g.clean_chest(limit=2, action="crack")
    assert res["cracked"] == 0 and res["skipped"] == 1
    g.confirm_if_needed.assert_called_once()


def test_crack_confirmed_counts_as_cleared():
    g = _chest_game([CHEST_ITEM, ITEM_CRACK, CONFIRM_PAGE, CHEST_EMPTY])
    g.body_text = Mock(return_value=CONFIRM_PAGE)
    g.confirm_if_needed = Mock(return_value=True)
    res = g.clean_chest(limit=2, action="crack")
    assert res["cracked"] == 1 and res["skipped"] == 0


JUNK_PAGE = (
    '<div>Куртка Дружинника редкий, новый</div>' + ITEM_CRACK +
    '<div>На мне надето Перчатки Берсерка мифический, Лучше (+370)</div>'
)
MYTHIC_PAGE = '<div>Бурка Ветерана мифический, новый</div>' + ITEM_CRACK


def test_epic_word_in_comparison_block_does_not_protect_junk():
    # На странице обычной вещи есть блок «На мне надето … мифический» —
    # из-за него хлам раньше считался наградным и не чистился.
    g = _chest_game([CHEST_ITEM, JUNK_PAGE, CHEST_EMPTY])
    g.confirm_if_needed = Mock(return_value=True)
    res = g.clean_chest(limit=2, action="crack")
    assert res["cracked"] == 1 and res["skipped"] == 0


def test_mythic_item_on_page_is_never_cracked():
    g = _chest_game([CHEST_ITEM, MYTHIC_PAGE, CHEST_EMPTY])
    res = g.clean_chest(limit=2, action="crack")
    assert res["cracked"] == 0 and res["dropped"] == 0
    g.click_href.assert_not_called()


def test_first_tier_reads_own_item_quality():
    g = Game({}, ".")
    assert g._first_tier("Куртка Дружинника редкий, новый") == "редкий"
    assert g._first_tier("Бурка Ветерана мифический, новый") == "мифический"
    assert g._first_tier("Шляпа Ополченца необычный, личный") == "необычный"


def _gear_agent(tmp_path, cleanup):
    cfg = json.loads((ROOT / "deploy/config-actions-steelblue.json").read_text(encoding="utf-8"))
    cfg["gear"]["chest_cleanup"] = cleanup
    cfg["_root"] = str(tmp_path)
    game = Mock()
    game.body_text.return_value = ""
    game.bag_counts.return_value = {"bag_used": 1, "bag_total": 20, "chest_used": 3, "chest_total": 20}
    return Agent(game, cfg, tmp_path / "logs")


def test_loop_cleans_chest_only_when_enabled(tmp_path):
    a = _gear_agent(tmp_path, "crack")
    a.game.clean_chest.return_value = {"cracked": 4, "dropped": 1, "skipped": 2}
    a._do_gear(rules.Decision("gear", params={"crack": False, "crack_chest": False}))
    a.game.clean_chest.assert_called_once()
    assert a.game.clean_chest.call_args.kwargs["action"] == "crack"


def test_loop_leaves_chest_alone_when_disabled(tmp_path):
    a = _gear_agent(tmp_path, "off")
    a._do_gear(rules.Decision("gear", params={"crack": False, "crack_chest": False}))
    a.game.clean_chest.assert_not_called()


def test_live_config_has_chest_cleanup_mode():
    cfg = json.loads((ROOT / "deploy/config-actions-steelblue.json").read_text(encoding="utf-8"))
    assert cfg["gear"]["chest_cleanup"] in ("crack", "drop", "off")
