

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
    g.p = SimpleNamespace(content=lambda: _shop_price_html(
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
    g.p = SimpleNamespace(content=lambda: _shop_price_html(
        '<img src="/images/icons/money_silver.png"><span>55</span>'
    ))
    ok, msg = g.buy_shop_item_capped("1", max_gold=1)
    assert ok is True
    assert "55" in msg
