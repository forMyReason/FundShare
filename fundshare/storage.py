from __future__ import annotations

import json
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
            self.save(DEFAULT_DB.copy())

    def load(self) -> dict[str, Any]:
        with self.db_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: dict[str, Any]) -> None:
        with self.db_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

