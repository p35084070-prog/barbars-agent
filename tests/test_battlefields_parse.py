"""Тесты парсера «Полей сражений»: бан, идущий бой, кнопка входа."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from barbars import pages  # noqa: E402


def test_ban_is_recognized():
    html = (
        "<html><body><div>Твой персонаж заходил в битву и не сражался на полях "
        "два или более раза. Вход на поля для тебя закрыт на 2д. 16ч.</div>"
        "<a href='../user'>Мой герой</a></body></html>"
    )
    info = pages.parse_battlefields(html, "")
    assert info["banned"] is True
    assert "2д" in info["ban_text"]
    assert info["fight_live"] is False
    assert info["join"] == []


def test_countdown_page_is_not_ban():
    html = (
        "<html><body>Поля сражений Следующее сражение: &quot;Штурм Крепости&quot; "
        "(12 на 12) Игра начнётся через:  00:16:20 Героев:  2  25 "
        "Бои на полях сражений доступны с 25 уровня Сегодня боёв: 0 "
        "Мои очки полей: 0"
        "<a href='../rating/bg'>Рейтинг полей</a>"
        "<a href='../game/bg/map/t/12'>Карта полей</a>"
        "<a href='../trade/ability'>Магазин умений</a>"
        "</body></html>"
    )
    info = pages.parse_battlefields(html, "")
    assert info["banned"] is False
    assert info["countdown"] == "00:16:20"
    assert info["fights_today"] == 0
    assert info["points"] == 0
    assert info["fight_live"] is False
    # служебные ссылки не должны считаться входом в бой
    assert info["join"] == []


def test_fight_live_without_join():
    html = (
        "<html><body>Поля сражений Следующее сражение: &quot;Штурм Крепости&quot; "
        "<a href='../rating/bg'>Рейтинг полей</a></body></html>"
    )
    info = pages.parse_battlefields(html, "")
    assert info["banned"] is False
    assert info["countdown"] == ""
    assert info["join"] == []
    assert info["fight_live"] is True
    assert info["in_combat"] is False


def test_in_combat_is_not_fight_live():
    html = (
        "<html><body>Поля сражений Ты ударил rudfos на 96 "
        "<a href='../?wicket:interface=:4:returnToGamePanel:currentGameLink::ILinkListener::'>"
        "Вернуться в бой</a></body></html>"
    )
    info = pages.parse_battlefields(html, "")
    assert info["in_combat"] is True
    assert info["fight_live"] is False


def test_join_button_detected():
    html = (
        "<html><body>Поля сражений "
        "<a href=\"../?wicket:interface=:5:bgPanel:joinLink::ILinkListener::\">В бой</a>"
        "</body></html>"
    )
    info = pages.parse_battlefields(html, "")
    assert len(info["join"]) == 1
    assert info["fight_live"] is False
