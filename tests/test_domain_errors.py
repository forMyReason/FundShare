from pathlib import Path

import pytest

from fundshare.errors import DomainError
from fundshare.service import PortfolioService
from fundshare.storage import JsonStorage


def test_domain_error_is_value_error_subclass() -> None:
    assert issubclass(DomainError, ValueError)


def test_duplicate_fund_raises_domain_error(tmp_path: Path) -> None:
    s = PortfolioService(JsonStorage(str(tmp_path / "d.json")))
    s.add_fund("780001", "A", 1.0, "2026-01-01")
    with pytest.raises(DomainError):
        s.add_fund("780001", "B", 1.0, "2026-01-02")


def test_delete_fund_when_no_position(tmp_path: Path) -> None:
    s = PortfolioService(JsonStorage(str(tmp_path / "del.json")))
    f = s.add_fund("780003", "待删", 1.0, "2026-01-01")
    s.add_buy(f["id"], "2026-01-02", "2026-01-03", 1.0, 10)
    s.add_sell(f["id"], "2026-01-04", "2026-01-05", 1.0, 10)
    s.delete_fund(f["id"])
    assert s.list_funds() == []


def test_delete_fund_blocked_when_holding(tmp_path: Path) -> None:
    s = PortfolioService(JsonStorage(str(tmp_path / "hold.json")))
    f = s.add_fund("780004", "持仓中", 1.0, "2026-01-01")
    s.add_buy(f["id"], "2026-01-02", "2026-01-03", 1.0, 10)
    with pytest.raises(DomainError):
        s.delete_fund(f["id"])
