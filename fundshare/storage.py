from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_DB = {
    "funds": [],
    "nav_points": [],
    "transactions": [],
    "next_ids": {"fund": 1, "nav": 1, "tx": 1},
}


class JsonStorage:
    def __init__(self, db_path: str = "data/store.json") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self.save(deepcopy(DEFAULT_DB))

    def load(self) -> dict[str, Any]:
        with self.db_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return self._normalize(data)

    def save(self, data: dict[str, Any]) -> None:
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        # Backward compatibility for old store.json created before nav_points/nav IDs were added.
        data.setdefault("funds", [])
        data.setdefault("transactions", [])
        data.setdefault("nav_points", [])
        data.setdefault("next_ids", {})
        data["next_ids"].setdefault("fund", self._next_from_items(data["funds"]))
        data["next_ids"].setdefault("tx", self._next_from_items(data["transactions"]))
        data["next_ids"].setdefault("nav", self._next_from_items(data["nav_points"]))
        for tx in data["transactions"]:
            legacy_date = tx.get("date", "")
            tx.setdefault("apply_date", legacy_date)
            tx.setdefault("confirm_date", legacy_date)
            tx.pop("date", None)
        return data

    @staticmethod
    def _next_from_items(items: list[dict[str, Any]]) -> int:
        if not items:
            return 1
        max_id = max(int(item.get("id", 0)) for item in items)
        return max_id + 1

