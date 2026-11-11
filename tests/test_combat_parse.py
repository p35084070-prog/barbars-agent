"""Оффлайн-тест боевого парсера на фикстуре с реальной разметкой игры."""

import json
from pathlib import Path

from barbars.driver import Game

FIXTURE = """
<div class="main">
<table><tbody><tr><td>
<img src="/images/icons/life.png" alt=""><span>3698</span>
<img src="/images/icons/energy.png" alt=""><span>3748</span>
</td></tr></tbody></table>
<table><tbody><tr>
<td><img class="bbl" src="/maneken?n=false&amp;sex=m" alt=""></td>
<td><img src="/images/icons/life.png" alt=""><span>5845</span></td>
</tr></tbody></table>
<div class="fbtn mb2"><a href="?wicket:interface=:42:actionPanel:damageLastTargetLink::ILinkListener::">
<span class="lbl">Бить  пью<br>обычный удар</span></a></div>
<div class="fbtn mb2"><a href="?wicket:interface=:42:actionPanel:abilityCombatPanel:ability:0:activateLink::ILinkListener::">
<span class="lbl">Bepcepк (гoтoво)<br>увеличивает урон</span></a></div>
<div class="fbtn mb2"><a href="?wicket:interface=:42:actionPanel:abilityCombatPanel:ability:1:activateLink::ILinkListener::">
<span class="lbl">Увoрот (20сек.)<br>уворот от удара</span></a></div>
<div class="fbtn mb2"><a href="?wicket:interface=:42:actionPanel:abilityCombatPanel:ability:2:activateLink::ILinkListener::">
<span class="lbl">Кaмeнный щит (гoтoво)<br>уменьшает урон</span></a></div>
<div class="fbtn mb2"><a href="?wicket:interface=:42:picturedUsePotionPanel:picturedUsePotionLink::ILinkListener::">
<span class="lbl">Пить бутылочку (290шт.)<br>восстанавливает здоровье</span></a></div>
<div>-207 +21</div>
<div>Ты ударил  пью на 904 крит</div>
<div>Ты исцелил себя на 49 [руна]</div>
<div> пью ударил тебя на 207</div>
</div>
"""

cfg = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))
game = Game(cfg, Path(__file__).resolve().parents[1] / "profile")
game.start(headless=True)
try:
    game.p.set_content(FIXTURE)
    cs = game.combat()
    assert cs.our_hp == 3698, cs.our_hp
    assert cs.our_energy == 3748, cs.our_energy
    assert cs.enemy_hp == 5845, cs.enemy_hp
    assert cs.enemy_name == "пью", repr(cs.enemy_name)
    assert cs.attack_links == ["Бить пью"], cs.attack_links
    ready = {a["name"]: a["ready"] for a in cs.abilities}
    assert ready.get("Bepcepк") is True, ready
    assert ready.get("Увoрот") is False, ready
    assert ready.get("Кaмeнный щит") is True, ready
    descs = {a["name"]: a["desc"] for a in cs.abilities}
    assert descs["Bepcepк"] == "увеличивает урон", descs
    assert cs.potion_links, cs.potion_links
    assert "Пить бутылочку" in cs.potion_links[0], cs.potion_links
    assert any("исцелил" in line for line in cs.log_lines), cs.log_lines
    assert any("904" in line for line in cs.log_lines), cs.log_lines
    print("combat parse: ok")
    print("  умения:", ready)
    print("  лог:", cs.log_lines)
finally:
    game.close()
print("Все оффлайн-проверки пройдены.")
