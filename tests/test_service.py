from pathlib import Path
import json

import pytest
import requests

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


def test_trade_date_order_validation(service: PortfolioService) -> None:
    fund = service.add_fund("100001", "日期校验", 1.0, "2026-01-01")
    with pytest.raises(ValueError):
        service.add_buy(fund["id"], "2026-01-03", "2026-01-02", 1.0, 1)


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


def test_apply_date_basis_changes_order_and_marker_date(service: PortfolioService) -> None:
    fund = service.add_fund("000005", "日期口径测试", 1.0, "2026-04-01")
    service.add_buy(fund["id"], "2026-04-10", "2026-04-12", 1.0, 100)
    service.add_buy(fund["id"], "2026-04-08", "2026-04-15", 1.1, 100)
    # confirm_date 排序下第二笔是后确认
    confirm_txs = service.get_transactions(fund["id"], date_field="confirm_date")
    assert confirm_txs[0]["price"] == 1.0
    # apply_date 排序下第二笔是后申请
    apply_txs = service.get_transactions(fund["id"], date_field="apply_date")
    assert apply_txs[0]["price"] == 1.1
    open_by_apply = service.get_open_buy_points(fund["id"], date_field="apply_date")
    assert open_by_apply[0]["date"] == "2026-04-08"


def test_invalid_date_field_raises(service: PortfolioService) -> None:
    fund = service.add_fund("000006", "口径异常测试", 1.0, "2026-04-01")
    with pytest.raises(ValueError):
        service.get_transactions(fund["id"], date_field="trade_date")


def test_duplicate_fund_code_rejected(service: PortfolioService) -> None:
    service.add_fund("200001", "重复代码基金", 1.0, "2026-04-01")
    with pytest.raises(ValueError):
        service.add_fund("200001", "重复代码基金2", 1.1, "2026-04-02")


def test_fund_code_format_validation(service: PortfolioService) -> None:
    with pytest.raises(ValueError):
        service.add_fund("abc", "格式错误", 1.0, "2026-04-01")
    with pytest.raises(ValueError):
        service.auto_fetch_fund_info("12345", "2026-04-01")
    assert service.normalize_fund_code(" 000001 ") == "000001"


def test_trade_price_and_shares_must_be_positive(service: PortfolioService) -> None:
    fund = service.add_fund("300001", "正数校验基金", 1.0, "2026-04-01")
    with pytest.raises(ValueError):
        service.add_buy(fund["id"], "2026-04-02", "2026-04-03", 0, 10)
    with pytest.raises(ValueError):
        service.add_sell(fund["id"], "2026-04-02", "2026-04-03", 1.0, 0)


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


def test_storage_migrates_legacy_transaction_date(tmp_path: Path) -> None:
    db_path = tmp_path / "store.json"
    db_path.write_text(
        (
            '{"funds":[{"id":1,"code":"1","name":"n","current_nav":1.0}],'
            '"transactions":[{"id":1,"fund_id":1,"tx_type":"buy","date":"2026-01-01","price":1.0,"shares":1.0,"amount":1.0}],'
            '"nav_points":[],"next_ids":{"fund":2,"tx":2,"nav":1}}'
        ),
        encoding="utf-8",
    )
    storage = JsonStorage(str(db_path))
    data = storage.load()
    tx = data["transactions"][0]
    assert tx["apply_date"] == "2026-01-01"
    assert tx["confirm_date"] == "2026-01-01"
    assert "date" not in tx


def test_storage_recovers_from_backup_when_primary_corrupted(tmp_path: Path) -> None:
    db_path = tmp_path / "store.json"
    storage = JsonStorage(str(db_path))
    data = storage.load()
    data["funds"].append({"id": 1, "code": "500001", "name": "恢复测试", "current_nav": 1.0})
    data["next_ids"]["fund"] = 2
    storage.save(data)

    # Corrupt primary file and ensure backup restore path works.
    db_path.write_text("{broken-json", encoding="utf-8")
    recovered = storage.load()
    assert recovered["funds"][0]["code"] == "500001"


def test_storage_creates_backup_on_save(tmp_path: Path) -> None:
    db_path = tmp_path / "store.json"
    storage = JsonStorage(str(db_path))
    data = storage.load()
    storage.save(data)
    backup_path = db_path.with_suffix(".json.bak")
    assert backup_path.exists()


def test_storage_rotated_backups_respect_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(JsonStorage, "MAX_ROTATED_BACKUPS", 3)
    db_path = tmp_path / "store.json"
    storage = JsonStorage(str(db_path))
    data = storage.load()
    for i in range(5):
        data["_test_stamp"] = i
        storage.save(data)
    rot_dir = db_path.parent / "backups"
    assert rot_dir.is_dir()
    assert len(list(rot_dir.glob("store_*.json"))) == 3


def test_data_persists_across_service_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "persist.json"
    s1 = PortfolioService(JsonStorage(str(db_path)))
    fund = s1.add_fund("400001", "重启持久化基金", 1.0, "2026-05-01")
    s1.add_buy(fund["id"], "2026-05-02", "2026-05-03", 1.01, 100)
    s1.add_sell(fund["id"], "2026-05-04", "2026-05-05", 1.02, 20)

    s2 = PortfolioService(JsonStorage(str(db_path)))
    funds = s2.list_funds()
    txs = s2.get_transactions(fund["id"])
    open_points = s2.get_open_buy_points(fund["id"])
    assert len(funds) == 1
    assert funds[0]["code"] == "400001"
    assert len(txs) == 2
    assert open_points[0]["remaining_shares"] == 80


def test_export_transactions_csv_contains_expected_columns_and_rows(service: PortfolioService) -> None:
    fund = service.add_fund("600001", "导出测试基金", 1.0, "2026-06-01")
    service.add_buy(fund["id"], "2026-06-02", "2026-06-03", 1.11, 10)
    service.add_sell(fund["id"], "2026-06-04", "2026-06-05", 1.12, 3)
    csv_text = service.export_transactions_csv(fund["id"])
    assert "tx_type,apply_date,confirm_date,price,shares,amount" in csv_text
    assert "buy,2026-06-02,2026-06-03,1.11,10.0,11.1" in csv_text
    assert "sell,2026-06-04,2026-06-05,1.12,3.0,3.36" in csv_text


def test_position_summary_calculation(service: PortfolioService) -> None:
    fund = service.add_fund("700001", "持仓汇总测试", 1.2, "2026-07-01")
    service.add_buy(fund["id"], "2026-07-02", "2026-07-03", 1.0, 100)
    service.add_buy(fund["id"], "2026-07-04", "2026-07-05", 1.1, 100)
    service.add_sell(fund["id"], "2026-07-06", "2026-07-07", 1.15, 80)
    summary = service.get_position_summary(fund["id"])
    assert summary["holding_shares"] == 120.0
    assert summary["holding_cost"] == 130.0
    assert summary["market_value"] == 144.0
    assert summary["floating_pnl"] == 14.0
    assert summary["avg_cost"] == 1.0833


def test_all_position_summaries_sorted_by_floating_pnl(service: PortfolioService) -> None:
    fund_a = service.add_fund("710001", "A基金", 1.2, "2026-07-01")
    fund_b = service.add_fund("710002", "B基金", 0.9, "2026-07-01")
    service.add_buy(fund_a["id"], "2026-07-02", "2026-07-03", 1.0, 100)
    service.add_buy(fund_b["id"], "2026-07-02", "2026-07-03", 1.0, 100)
    rows = service.get_all_position_summaries()
    assert len(rows) == 2
    assert rows[0]["code"] == "710001"
    assert rows[1]["code"] == "710002"


def test_get_remaining_shares(service: PortfolioService) -> None:
    fund = service.add_fund("720001", "剩余份额测试", 1.0, "2026-07-01")
    service.add_buy(fund["id"], "2026-07-02", "2026-07-03", 1.0, 50)
    service.add_sell(fund["id"], "2026-07-04", "2026-07-05", 1.1, 10)
    assert service.get_remaining_shares(fund["id"]) == 40.0


def test_filter_transactions_by_date_range(service: PortfolioService) -> None:
    fund = service.add_fund("750001", "日期筛选测试", 1.0, "2026-07-01")
    service.add_buy(fund["id"], "2026-07-02", "2026-07-03", 1.0, 10)
    service.add_sell(fund["id"], "2026-07-04", "2026-07-05", 1.1, 5)
    service.add_buy(fund["id"], "2026-07-06", "2026-07-07", 1.2, 10)
    rows = service.filter_transactions_by_date_range(
        fund["id"], "2026-07-04", "2026-07-07", date_field="confirm_date"
    )
    assert len(rows) == 2
    assert rows[0]["tx_type"] == "sell"
    assert rows[1]["tx_type"] == "buy"


def test_filter_transactions_date_range_validation(service: PortfolioService) -> None:
    fund = service.add_fund("750002", "日期范围校验", 1.0, "2026-07-01")
    with pytest.raises(ValueError):
        service.filter_transactions_by_date_range(
            fund["id"], "2026-07-10", "2026-07-01", date_field="confirm_date"
        )


def test_filter_transactions_by_type(service: PortfolioService) -> None:
    fund = service.add_fund("750003", "类型筛选测试", 1.0, "2026-07-01")
    service.add_buy(fund["id"], "2026-07-02", "2026-07-03", 1.0, 10)
    service.add_sell(fund["id"], "2026-07-04", "2026-07-05", 1.1, 5)
    txs = service.get_transactions(fund["id"])
    assert len(service.filter_transactions_by_type(txs, "buy")) == 1
    assert len(service.filter_transactions_by_type(txs, "sell")) == 1
    assert len(service.filter_transactions_by_type(txs, "all")) == 2
    with pytest.raises(ValueError):
        service.filter_transactions_by_type(txs, "x")


def test_classify_sell_risk_levels() -> None:
    assert PortfolioService.classify_sell_risk(100.0, 30.0) == "none"
    assert PortfolioService.classify_sell_risk(100.0, 50.0) == "large"
    assert PortfolioService.classify_sell_risk(100.0, 100.0) == "clearout"
    assert PortfolioService.classify_sell_risk(100.0, 49.99, eps=1e-6) == "none"
    assert PortfolioService.classify_sell_risk(0.0, 10.0) == "none"


def test_filter_records_by_date_range_static() -> None:
    rows = [{"date": "2026-01-01"}, {"date": "2026-06-01"}, {"date": "2026-12-01"}]
    filtered = PortfolioService.filter_records_by_date_range(rows, "date", "2026-03-01", "2026-09-01")
    assert [r["date"] for r in filtered] == ["2026-06-01"]


def test_nav_chart_date_window_presets() -> None:
    pts = [{"date": "2026-01-01", "nav": 1.0}, {"date": "2026-12-31", "nav": 1.2}]
    assert PortfolioService.nav_chart_date_window(pts, "全部") == (None, None)
    start, end = PortfolioService.nav_chart_date_window(pts, "近1月")
    assert end == "2026-12-31"
    assert start == "2026-12-01"


def test_nav_point_calendar_gaps_detection() -> None:
    pts = [
        {"date": "2026-01-01", "nav": 1.0},
        {"date": "2026-01-10", "nav": 1.05},
    ]
    assert PortfolioService.nav_point_calendar_gaps(pts, min_gap_days=14) == []
    pts2 = [
        {"date": "2026-01-01", "nav": 1.0},
        {"date": "2026-03-01", "nav": 1.1},
    ]
    gaps = PortfolioService.nav_point_calendar_gaps(pts2, min_gap_days=14)
    assert len(gaps) == 1
    assert gaps[0][0] == "2026-01-01"
    assert gaps[0][1] == "2026-03-01"
    assert gaps[0][2] == 59


def test_export_portfolio_csv(service: PortfolioService) -> None:
    f = service.add_fund("760001", "导出组合", 1.1, "2026-08-01")
    service.add_buy(f["id"], "2026-08-02", "2026-08-03", 1.0, 10)
    text = service.export_portfolio_csv()
    assert "code,name,holding_shares" in text.replace("\r\n", "\n")
    assert "760001" in text
    assert "1.1" in text


def test_import_transactions_json_success(service: PortfolioService) -> None:
    f = service.add_fund("770001", "JSON导入", 1.0, "2026-01-01")
    payload = json.dumps(
        {
            "fund_code": "770001",
            "transactions": [
                {
                    "tx_type": "buy",
                    "apply_date": "2026-02-01",
                    "confirm_date": "2026-02-02",
                    "price": 1.0,
                    "shares": 10.0,
                },
            ],
        }
    )
    assert service.import_transactions_json(payload) == 1
    assert len(service.get_transactions(f["id"])) == 1


def test_import_transactions_json_validation(service: PortfolioService) -> None:
    service.add_fund("770002", "校验", 1.0, "2026-01-01")
    with pytest.raises(ValueError):
        service.import_transactions_json("{}")
    with pytest.raises(ValueError):
        service.import_transactions_json('{"fund_code":"770002","transactions":[]}')
    bad = json.dumps(
        {
            "fund_code": "770002",
            "transactions": [{"tx_type": "buy", "apply_date": "x", "confirm_date": "2026-02-02", "price": 1, "shares": 1}],
        }
    )
    with pytest.raises(ValueError):
        service.import_transactions_json(bad)


def test_portfolio_overview_aggregates_totals(service: PortfolioService) -> None:
    a = service.add_fund("730001", "组合A", 1.2, "2026-07-01")
    b = service.add_fund("730002", "组合B", 0.8, "2026-07-01")
    service.add_buy(a["id"], "2026-07-02", "2026-07-03", 1.0, 100)
    service.add_buy(b["id"], "2026-07-02", "2026-07-03", 1.0, 50)
    overview = service.get_portfolio_overview()
    assert overview["total_cost"] == 150.0
    assert overview["total_value"] == 160.0
    assert overview["total_pnl"] == 10.0
    assert overview["pnl_ratio"] == 0.066667
    assert overview["buy_amount"] == 150.0
    assert overview["sell_amount"] == 0.0
    assert overview["realized_pnl"] == 0.0


def test_portfolio_overview_realized_pnl(service: PortfolioService) -> None:
    f = service.add_fund("740001", "已实现盈亏测试", 1.3, "2026-07-01")
    service.add_buy(f["id"], "2026-07-02", "2026-07-03", 1.0, 100)  # buy 100
    service.add_sell(f["id"], "2026-07-04", "2026-07-05", 1.2, 60)   # sell 72
    overview = service.get_portfolio_overview()
    assert overview["buy_amount"] == 100.0
    assert overview["sell_amount"] == 72.0
    assert overview["total_cost"] == 40.0
    assert overview["realized_pnl"] == 12.0


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


def test_fund_api_empty_code_raises() -> None:
    client = FundApiClient()
    with pytest.raises(ValueError):
        client.fetch_name_and_nav("", "2024-04-01")


def test_fund_api_missing_name_raises() -> None:
    with pytest.raises(ValueError):
        FundApiClient._extract_name("var other='x';")


def test_fund_api_missing_trend_raises() -> None:
    js_text = 'var fS_name = "示例基金";'
    with pytest.raises(ValueError):
        FundApiClient._extract_nav_for_date(js_text, "2024-04-01")


def test_fund_api_empty_trend_raises() -> None:
    js_text = 'var Data_netWorthTrend = [];'
    with pytest.raises(ValueError):
        FundApiClient._extract_nav_for_date(js_text, "2024-04-01")


def test_fund_api_target_before_all_data_raises() -> None:
    js_text = 'var Data_netWorthTrend = [{"x":1711987200000,"y":1.3}];'
    with pytest.raises(ValueError):
        FundApiClient._extract_nav_for_date(js_text, "2024-03-31")


def test_fund_api_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        text = ""

        @staticmethod
        def raise_for_status() -> None:
            raise requests.HTTPError("boom")

    def _fake_get(url: str, timeout: float):  # noqa: ANN001
        return _Resp()

    monkeypatch.setattr(requests, "get", _fake_get)
    client = FundApiClient()
    with pytest.raises(requests.HTTPError):
        client.fetch_name_and_nav("000001", "2024-04-01")

