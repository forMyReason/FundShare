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
    bad_alloc = 0
    txs = data.get("transactions", [])
    buy_map = {int(t["id"]): t for t in txs if t.get("tx_type") == "buy"}
    sold_by_buy: dict[int, float] = {}
    for t in txs:
        if t.get("tx_type") != "sell":
            continue
        allocs = t.get("allocations") or []
        if not allocs:
            continue
        alloc_sum = 0.0
        for a in allocs:
            try:
                bid = int(a["buy_tx_id"])
                sh = float(a["shares"])
            except (KeyError, TypeError, ValueError):
                bad_alloc += 1
                continue
            alloc_sum += sh
            if bid not in buy_map:
                bad_alloc += 1
                continue
            sold_by_buy[bid] = sold_by_buy.get(bid, 0.0) + sh
        if abs(alloc_sum - float(t.get("shares", 0.0))) > 1e-6:
            bad_alloc += 1
    for bid, sold in sold_by_buy.items():
        if sold - float(buy_map[bid].get("shares", 0.0)) > 1e-6:
            bad_alloc += 1
    ok = True
    if bad_tx:
        ok = False
        print(f"orphan transactions: {len(bad_tx)} (fund_id not in funds)", file=sys.stderr)
    if bad_nav:
        ok = False
        print(f"orphan nav_points: {len(bad_nav)} (fund_id not in funds)", file=sys.stderr)
    if bad_alloc:
        ok = False
        print(f"invalid allocations: {bad_alloc} (sum mismatch / bad buy_tx_id / over-allocated)", file=sys.stderr)
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
