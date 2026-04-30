import subprocess
import sys
from pathlib import Path

from fundshare.check_data import run_check
from fundshare.storage import JsonStorage


def _minimal_fund() -> dict:
    return {"id": 1, "code": "000001", "name": "n", "current_nav": 1.0}


def _buy(tid: int, shares: float) -> dict:
    return {
        "id": tid,
        "fund_id": 1,
        "tx_type": "buy",
        "apply_date": "2026-01-01",
        "confirm_date": "2026-01-01",
        "price": 1.0,
        "shares": shares,
        "amount": shares,
        "fee": 0.0,
    }


def _sell(tid: int, shares: float, allocations: list) -> dict:
    return {
        "id": tid,
        "fund_id": 1,
        "tx_type": "sell",
        "apply_date": "2026-01-02",
        "confirm_date": "2026-01-02",
        "price": 1.0,
        "shares": shares,
        "amount": shares,
        "fee": 0.0,
        "allocations": allocations,
    }


def test_run_check_ok_on_clean_store(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [{"id": 1, "code": "000001", "name": "n", "current_nav": 1.0}]
    data["transactions"] = []
    data["nav_points"] = []
    data["next_ids"] = {"fund": 2, "tx": 1, "nav": 1}
    s.save(data)
    assert run_check(str(db)) == 0


def test_run_check_fails_on_orphan_transaction(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [{"id": 1, "code": "000001", "name": "n", "current_nav": 1.0}]
    data["transactions"] = [
        {
            "id": 1,
            "fund_id": 99,
            "tx_type": "buy",
            "apply_date": "2026-01-01",
            "confirm_date": "2026-01-02",
            "price": 1.0,
            "shares": 1.0,
            "amount": 1.0,
            "fee": 0.0,
        }
    ]
    data["nav_points"] = []
    data["next_ids"] = {"fund": 2, "tx": 2, "nav": 1}
    s.save(data)
    assert run_check(str(db)) == 1


def test_run_check_fails_on_orphan_nav_point(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [{"id": 1, "code": "000001", "name": "n", "current_nav": 1.0}]
    data["transactions"] = []
    data["nav_points"] = [{"id": 1, "fund_id": 42, "date": "2026-01-01", "nav": 1.0}]
    data["next_ids"] = {"fund": 2, "tx": 1, "nav": 2}
    s.save(data)
    assert run_check(str(db)) == 1


def test_run_check_fails_on_invalid_allocations(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [{"id": 1, "code": "000001", "name": "n", "current_nav": 1.0}]
    data["transactions"] = [
        {
            "id": 1,
            "fund_id": 1,
            "tx_type": "buy",
            "apply_date": "2026-01-01",
            "confirm_date": "2026-01-01",
            "price": 1.0,
            "shares": 10.0,
            "amount": 10.0,
            "fee": 0.0,
            "allocations": [],
        },
        {
            "id": 2,
            "fund_id": 1,
            "tx_type": "sell",
            "apply_date": "2026-01-02",
            "confirm_date": "2026-01-02",
            "price": 1.0,
            "shares": 3.0,
            "amount": 3.0,
            "fee": 0.0,
            "allocations": [{"buy_tx_id": 1, "shares": 9.0}],
        },
    ]
    data["nav_points"] = []
    data["next_ids"] = {"fund": 2, "tx": 3, "nav": 1}
    s.save(data)
    assert run_check(str(db)) == 1


def test_run_check_allocation_unknown_buy_tx_id(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [_minimal_fund()]
    data["transactions"] = [
        _buy(1, 10.0),
        _sell(2, 1.0, [{"buy_tx_id": 99, "shares": 1.0}]),
    ]
    data["nav_points"] = []
    data["next_ids"] = {"fund": 2, "tx": 3, "nav": 1}
    s.save(data)
    assert run_check(str(db)) == 1


def test_run_check_oversell_against_buy(tmp_path: Path) -> None:
    """Cumulative allocated sell shares exceed the referenced buy's shares."""
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [_minimal_fund()]
    data["transactions"] = [
        _buy(1, 10.0),
        _sell(2, 6.0, [{"buy_tx_id": 1, "shares": 4.0}]),
        _sell(3, 6.0, [{"buy_tx_id": 1, "shares": 6.0}]),
    ]
    data["nav_points"] = []
    data["next_ids"] = {"fund": 2, "tx": 4, "nav": 1}
    s.save(data)
    assert run_check(str(db)) == 1


def test_check_data_main_module_exits_with_code(tmp_path: Path) -> None:
    """CLI entry: python -m fundshare.check_data --db <path>"""
    db = tmp_path / "store.json"
    s = JsonStorage(str(db))
    data = s.load()
    data["funds"] = [_minimal_fund()]
    data["transactions"] = []
    data["nav_points"] = []
    data["next_ids"] = {"fund": 2, "tx": 1, "nav": 1}
    s.save(data)
    r = subprocess.run(
        [sys.executable, "-m", "fundshare.check_data", "--db", str(db)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0

    db_bad = tmp_path / "bad.json"
    s2 = JsonStorage(str(db_bad))
    data2 = s2.load()
    data2["funds"] = []
    data2["transactions"] = [
        {
            "id": 1,
            "fund_id": 1,
            "tx_type": "buy",
            "apply_date": "2026-01-01",
            "confirm_date": "2026-01-01",
            "price": 1.0,
            "shares": 1.0,
            "amount": 1.0,
            "fee": 0.0,
        }
    ]
    data2["nav_points"] = []
    data2["next_ids"] = {"fund": 2, "tx": 2, "nav": 1}
    s2.save(data2)
    r2 = subprocess.run(
        [sys.executable, "-m", "fundshare.check_data", "--db", str(db_bad)],
        capture_output=True,
        text=True,
    )
    assert r2.returncode == 1
