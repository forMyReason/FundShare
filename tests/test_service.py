from pathlib import Path

import pytest

from fundshare.service import PortfolioService
from fundshare.storage import JsonStorage


@pytest.fixture()
def service(tmp_path: Path) -> PortfolioService:
    storage = JsonStorage(str(tmp_path / "store.json"))
    return PortfolioService(storage)


def test_buy_amount_auto_calculated(service: PortfolioService) -> None:
    fund = service.add_fund("000001", "测试基金", 1.2, "2026-01-01")
    buy = service.add_buy(fund["id"], "2026-01-02", 1.1, 100)
    assert buy["amount"] == 110.0


def test_sell_must_not_exceed_holding(service: PortfolioService) -> None:
    fund = service.add_fund("000001", "测试基金", 1.2, "2026-01-01")
    service.add_buy(fund["id"], "2026-01-02", 1.1, 100)
    with pytest.raises(ValueError):
        service.add_sell(fund["id"], "2026-01-03", 1.3, 120)


def test_fifo_consumption_and_open_buy_points(service: PortfolioService) -> None:
    fund = service.add_fund("000001", "测试基金", 1.2, "2026-01-01")
    service.add_buy(fund["id"], "2026-01-02", 1.0, 100)
    service.add_buy(fund["id"], "2026-01-03", 1.1, 200)
    service.add_sell(fund["id"], "2026-01-04", 1.2, 150)

    open_points = service.get_open_buy_points(fund["id"])
    assert len(open_points) == 1
    assert open_points[0]["price"] == 1.1
    assert open_points[0]["remaining_shares"] == 150

