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
