from fundshare.money import MONEY_DECIMALS, q_money, q_ratio


def test_q_money_rounds_to_configured_decimals() -> None:
    assert q_money(1.234567) == round(1.234567, MONEY_DECIMALS)


def test_q_ratio_rounds_to_configured_decimals() -> None:
    assert q_ratio(0.066666666) == 0.066667
