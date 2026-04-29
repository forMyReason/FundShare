from pathlib import Path

from fundshare.check_data import run_check
from fundshare.storage import JsonStorage


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
