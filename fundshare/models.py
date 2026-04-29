from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Literal


TxType = Literal["buy", "sell"]


@dataclass
class Fund:
    id: int
    code: str
    name: str
    current_nav: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NavPoint:
    id: int
    fund_id: int
    date: str
    nav: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Transaction:
    id: int
    fund_id: int
    tx_type: TxType
    apply_date: str
    confirm_date: str
    price: float
    shares: float
    amount: float
    fee: float
    allocations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

