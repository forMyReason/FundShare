"""End-to-end style tests over public service API (no Streamlit)."""

from pathlib import Path

from fundshare.service import PortfolioService
from fundshare.storage import JsonStorage


def test_e2e_add_fund_buy_sell_export_overview(tmp_path: Path) -> None:
    db = tmp_path / "e2e.json"
    s = PortfolioService(JsonStorage(str(db)))
    f = s.add_fund("790001", "端到端基金", 1.05, "2026-01-01")
    s.add_buy(f["id"], "2026-01-02", "2026-01-03", 1.0, 200)
    s.add_sell(f["id"], "2026-01-04", "2026-01-05", 1.02, 50)
    assert s.get_remaining_shares(f["id"]) == 150.0
    csv_tx = s.export_transactions_csv(f["id"])
    assert "buy" in csv_tx and "sell" in csv_tx
    port = s.export_portfolio_csv()
    assert "790001" in port
    ov = s.get_portfolio_overview()
    assert ov["buy_amount"] >= 200.0
    assert ov["sell_amount"] >= 51.0
