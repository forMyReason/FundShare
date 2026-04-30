from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _import_bridge() -> object:
    root = Path(__file__).resolve().parents[1]
    bridge_dir = root / "android" / "app" / "src" / "main" / "python"
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    import fundshare_android.bridge as bridge  # type: ignore

    return bridge


def test_trades_payload_empty_without_fund(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = _import_bridge()
    payload = json.loads(bridge.trades_payload_json_safe("{}"))
    assert payload["funds"] == []
    assert "empty_reason" in payload


def test_trades_rpc_add_buy_and_payload_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = _import_bridge()
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    svc = PortfolioService(JsonStorage())
    fund = svc.add_fund("000001", "示例基金", 1.0, "2026-01-01")
    fund_id = int(fund["id"])

    r = json.loads(
        bridge.trades_rpc(
            "add_buy",
            json.dumps(
                {
                    "fund_id": fund_id,
                    "confirm_date": "2026-01-02",
                    "price": 1.2,
                    "shares": 100,
                    "fee": 0.1,
                }
            ),
        )
    )
    assert r["ok"] is True

    payload = json.loads(
        bridge.trades_payload_json_safe(
            json.dumps({"fund_id": fund_id, "tx_start": "2026-01-01", "tx_end": "2026-12-31"})
        )
    )
    assert int(payload["selected_fund_id"]) == fund_id
    assert len(payload["transactions"]) == 1
    assert payload["transactions"][0]["tx_type"] == "buy"


def test_trades_rpc_export_csv_contains_headers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = _import_bridge()
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    svc = PortfolioService(JsonStorage())
    fund = svc.add_fund("000002", "导出测试", 1.0, "2026-01-01")
    fund_id = int(fund["id"])
    svc.add_buy(fund_id, "2026-01-01", "2026-01-01", 1.0, 10.0, 0.0)

    r = json.loads(bridge.trades_rpc("export_csv", json.dumps({"fund_id": fund_id})))
    assert r["ok"] is True
    csv_text = r["data"]["csv_text"]
    assert "tx_type" in csv_text
    assert "confirm_date" in csv_text


def test_trades_rpc_add_sell_by_lots_rejects_invalid_picks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = _import_bridge()
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    svc = PortfolioService(JsonStorage())
    fund = svc.add_fund("000003", "批次卖出测试", 1.0, "2026-01-01")
    fund_id = int(fund["id"])
    svc.add_buy(fund_id, "2026-01-01", "2026-01-02", 1.2, 100.0, 0.0)

    bad = json.loads(
        bridge.trades_rpc(
            "add_sell_by_lots",
            json.dumps(
                {
                    "fund_id": fund_id,
                    "confirm_date": "2026-01-05",
                    "price": 1.3,
                    "picks": [{"buy_tx_id": 0, "shares": 10}],
                }
            ),
        )
    )
    assert bad["ok"] is False
    assert "无效" in bad["error"]


def test_trades_rpc_add_buy_rejects_invalid_date(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    bridge = _import_bridge()
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    svc = PortfolioService(JsonStorage())
    fund = svc.add_fund("000004", "日期校验测试", 1.0, "2026-01-01")
    fund_id = int(fund["id"])

    bad = json.loads(
        bridge.trades_rpc(
            "add_buy",
            json.dumps(
                {
                    "fund_id": fund_id,
                    "confirm_date": "2026/01/02",
                    "price": 1.2,
                    "shares": 100,
                    "fee": 0.1,
                }
            ),
        )
    )
    assert bad["ok"] is False
