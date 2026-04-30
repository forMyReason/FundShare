"""JsonStorage edge paths: DATA_DIR, corrupt primary + .bak recovery."""

import json
from pathlib import Path

import pytest

from fundshare.storage import DEFAULT_DB, JsonStorage, default_store_path


def test_default_store_path_without_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    assert default_store_path() == "data/store.json"


def test_default_store_path_with_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert default_store_path() == str(tmp_path / "store.json")


def test_load_corrupt_json_restores_from_bak(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    bak = tmp_path / "store.json.bak"
    good = dict(DEFAULT_DB)
    good["funds"] = [{"id": 1, "code": "x", "name": "n", "current_nav": 1.0}]
    bak.write_text(json.dumps(good), encoding="utf-8")
    db.write_text("{not json", encoding="utf-8")

    st = JsonStorage(str(db))
    data = st.load()
    assert data["funds"][0]["code"] == "x"
    # Primary file rewritten from backup
    roundtrip = json.loads(db.read_text(encoding="utf-8"))
    assert roundtrip["funds"][0]["code"] == "x"


def test_load_corrupt_json_without_bak_raises(tmp_path: Path) -> None:
    db = tmp_path / "store.json"
    db.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        JsonStorage(str(db)).load()


def test_normalize_cleans_malformed_allocations(tmp_path: Path) -> None:
    """Non-list allocations and non-dict items are dropped; valid rows kept."""
    db = tmp_path / "store.json"
    st = JsonStorage(str(db))
    d = st.load()
    d["funds"] = [{"id": 1, "code": "c", "name": "n", "current_nav": 1.0}]
    d["transactions"] = [
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
            "allocations": "garbage",
        }
    ]
    d["next_ids"] = {"fund": 2, "tx": 2, "nav": 1}
    st.save(d)
    d2 = st.load()
    assert d2["transactions"][0]["allocations"] == []

    d3 = st.load()
    d3["transactions"] = [
        {
            "id": 1,
            "fund_id": 1,
            "tx_type": "sell",
            "apply_date": "2026-01-02",
            "confirm_date": "2026-01-02",
            "price": 1.0,
            "shares": 1.0,
            "amount": 1.0,
            "fee": 0.0,
            "allocations": [42, {"buy_tx_id": 9, "shares": 1.0}],
        }
    ]
    st.save(d3)
    out = st.load()
    assert out["transactions"][0]["allocations"] == [{"buy_tx_id": 9, "shares": 1.0}]


def test_normalize_drops_allocations_with_invalid_types(tmp_path: Path) -> None:
    """Invalid shares/buy_tx_id types are skipped (storage.py except branch)."""
    db = tmp_path / "store.json"
    st = JsonStorage(str(db))
    d = st.load()
    d["funds"] = [{"id": 1, "code": "c", "name": "n", "current_nav": 1.0}]
    d["transactions"] = [
        {
            "id": 1,
            "fund_id": 1,
            "tx_type": "sell",
            "apply_date": "2026-01-02",
            "confirm_date": "2026-01-02",
            "price": 1.0,
            "shares": 1.0,
            "amount": 1.0,
            "fee": 0.0,
            "allocations": [
                {"buy_tx_id": 1, "shares": 1.0},
                {"buy_tx_id": 1, "shares": "not-a-number"},
            ],
        }
    ]
    d["next_ids"] = {"fund": 2, "tx": 2, "nav": 1}
    st.save(d)
    out = st.load()
    assert out["transactions"][0]["allocations"] == [{"buy_tx_id": 1, "shares": 1.0}]
