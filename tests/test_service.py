from pathlib import Path

import pytest

from fundshare.fund_api import FundApiClient
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


def test_storage_normalizes_old_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "store.json"
    db_path.write_text(
        '{"funds":[],"transactions":[],"next_ids":{"fund":1,"tx":1}}',
        encoding="utf-8",
    )
    storage = JsonStorage(str(db_path))
    data = storage.load()
    assert "nav_points" in data
    assert "nav" in data["next_ids"]
    assert data["next_ids"]["nav"] == 1


def test_auto_fetch_fund_info_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    sample_js = """
    var fS_name = "示例基金";
    var Data_netWorthTrend = [{"x":1711900800000,"y":1.2345},{"x":1711987200000,"y":1.3}];
    """

    def _fake_fetch(self, code: str) -> str:  # noqa: ANN001
        return sample_js

    monkeypatch.setattr(FundApiClient, "_fetch_fund_js", _fake_fetch)
    client = FundApiClient()
    name, nav = client.fetch_name_and_nav("000001", "2024-04-01")
    assert name == "示例基金"
    assert nav == 1.2345

