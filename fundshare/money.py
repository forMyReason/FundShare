"""Centralised decimal rounding for money-like fields."""

MONEY_DECIMALS = 4
RATIO_DECIMALS = 6


def q_money(value: float) -> float:
    return round(float(value), MONEY_DECIMALS)


def q_ratio(value: float) -> float:
    return round(float(value), RATIO_DECIMALS)
