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
    buy = service.add_buy(fund["id"], "2026-01-02", "2026-01-03", 1.1, 100)
    assert buy["amount"] == 110.0


def test_sell_must_not_exceed_holding(service: PortfolioService) -> None:
    fund = service.add_fund("000001", "测试基金", 1.2, "2026-01-01")
    service.add_buy(fund["id"], "2026-01-02", "2026-01-03", 1.1, 100)
    with pytest.raises(ValueError):
        service.add_sell(fund["id"], "2026-01-04", "2026-01-05", 1.3, 120)


def test_fifo_consumption_and_open_buy_points(service: PortfolioService) -> None:
    fund = service.add_fund("000001", "测试基金", 1.2, "2026-01-01")
    service.add_buy(fund["id"], "2026-01-02", "2026-01-03", 1.0, 100)
    service.add_buy(fund["id"], "2026-01-04", "2026-01-05", 1.1, 200)
    service.add_sell(fund["id"], "2026-01-06", "2026-01-07", 1.2, 150)

    open_points = service.get_open_buy_points(fund["id"])
    assert len(open_points) == 1
    assert open_points[0]["date"] == "2026-01-05"
    assert open_points[0]["price"] == 1.1
    assert open_points[0]["remaining_shares"] == 150


def test_save_and_read_buy_sell_records(service: PortfolioService) -> None:
    fund = service.add_fund("000002", "保存读取测试", 1.0, "2026-01-01")
    service.add_buy(fund["id"], "2026-01-10", "2026-01-11", 1.02, 100)
    service.add_sell(fund["id"], "2026-01-12", "2026-01-13", 1.03, 30)
    txs = service.get_transactions(fund["id"])
    assert len(txs) == 2
    assert txs[0]["tx_type"] == "buy"
    assert txs[0]["apply_date"] == "2026-01-10"
    assert txs[0]["confirm_date"] == "2026-01-11"
    assert txs[1]["tx_type"] == "sell"
    assert txs[1]["apply_date"] == "2026-01-12"
    assert txs[1]["confirm_date"] == "2026-01-13"


def test_chart_open_points_show_and_hide(service: PortfolioService) -> None:
    fund = service.add_fund("000003", "图表买点测试", 1.0, "2026-01-01")
    service.add_buy(fund["id"], "2026-02-01", "2026-02-02", 1.01, 50)
    service.add_buy(fund["id"], "2026-02-03", "2026-02-04", 1.02, 50)
    assert len(service.get_open_buy_points(fund["id"])) == 2
    service.add_sell(fund["id"], "2026-02-05", "2026-02-06", 1.03, 50)
    open_points = service.get_open_buy_points(fund["id"])
    assert len(open_points) == 1
    assert open_points[0]["price"] == 1.02
    service.add_sell(fund["id"], "2026-02-07", "2026-02-08", 1.04, 50)
    assert service.get_open_buy_points(fund["id"]) == []


def test_simulated_user_flow(service: PortfolioService) -> None:
    fund = service.add_fund("000004", "模拟用户流程", 1.2, "2026-03-01")
    service.update_fund_nav(fund["id"], 1.21, "2026-03-02")
    service.update_fund_nav(fund["id"], 1.18, "2026-03-03")
    service.add_buy(fund["id"], "2026-03-02", "2026-03-03", 1.21, 100)
    service.add_buy(fund["id"], "2026-03-04", "2026-03-05", 1.18, 100)
    service.add_sell(fund["id"], "2026-03-06", "2026-03-07", 1.25, 120)
    open_points = service.get_open_buy_points(fund["id"])
    assert len(open_points) == 1
    assert open_points[0]["remaining_shares"] == 80


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

