from __future__ import annotations

import argparse
import sys
from typing import Any

from .storage import JsonStorage


def run_check(db_path: str | None = None) -> int:
    """Return 0 if store looks consistent, 1 if orphan records found."""
    store = JsonStorage(db_path) if db_path else JsonStorage()
    data: dict[str, Any] = store.load()
    fund_ids = {int(f["id"]) for f in data.get("funds", [])}
    bad_tx = [t for t in data.get("transactions", []) if int(t["fund_id"]) not in fund_ids]
    bad_nav = [p for p in data.get("nav_points", []) if int(p["fund_id"]) not in fund_ids]
    ok = True
    if bad_tx:
        ok = False
        print(f"orphan transactions: {len(bad_tx)} (fund_id not in funds)", file=sys.stderr)
    if bad_nav:
        ok = False
        print(f"orphan nav_points: {len(bad_nav)} (fund_id not in funds)", file=sys.stderr)
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="FundShare JSON store integrity check (orphan rows).")
    parser.add_argument(
        "--db",
        default=None,
        help="Path to store.json (default: from DATA_DIR or data/store.json)",
    )
    args = parser.parse_args()
    raise SystemExit(run_check(args.db))


if __name__ == "__main__":
    main()
