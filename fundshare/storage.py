from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DB = {
    "funds": [],
    "nav_points": [],
    "transactions": [],
    "next_ids": {"fund": 1, "nav": 1, "tx": 1},
}


def default_store_path() -> str:
    """Primary DB file; if env ``DATA_DIR`` is set, use ``<DATA_DIR>/store.json``."""
    raw = (os.environ.get("DATA_DIR") or "").strip()
    if not raw:
        return "data/store.json"
    return str(Path(raw).expanduser() / "store.json")


class JsonStorage:
    MAX_ROTATED_BACKUPS = 10

    def __init__(self, db_path: str | None = None) -> None:
        path_str = db_path if db_path is not None else default_store_path()
        self.db_path = Path(path_str)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self.save(deepcopy(DEFAULT_DB))

    def load(self) -> dict[str, Any]:
        try:
            with self.db_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            backup = self._backup_path()
            if not backup.exists():
                raise
            with backup.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Restore corrupted primary file from backup.
            self._atomic_write(data)
        return self._normalize(data)

    def save(self, data: dict[str, Any]) -> None:
        self._atomic_write(data)
        text = self.db_path.read_text(encoding="utf-8")
        self._backup_path().write_text(text, encoding="utf-8")
        self._append_rotated_backup(text)

    def _backup_dir(self) -> Path:
        return self.db_path.parent / "backups"

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
            tx.setdefault("fee", 0.0)
            tx.setdefault("allocations", [])
            if not isinstance(tx["allocations"], list):
                tx["allocations"] = []
            cleaned: list[dict[str, Any]] = []
            for a in tx["allocations"]:
                if not isinstance(a, dict):
                    continue
                try:
                    cleaned.append(
                        {
                            "buy_tx_id": int(a["buy_tx_id"]),
                            "shares": float(a["shares"]),
                        }
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            tx["allocations"] = cleaned
        return data

    @staticmethod
    def _next_from_items(items: list[dict[str, Any]]) -> int:
        if not items:
            return 1
        max_id = max(int(item.get("id", 0)) for item in items)
        return max_id + 1

    def _backup_path(self) -> Path:
        return self.db_path.with_suffix(self.db_path.suffix + ".bak")

    def _append_rotated_backup(self, text: str) -> None:
        backup_root = self._backup_dir()
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = backup_root / f"{self.db_path.stem}_{stamp}.json"
        dest.write_text(text, encoding="utf-8")
        pattern = f"{self.db_path.stem}_*.json"
        files = sorted(backup_root.glob(pattern))
        cutoff = max(0, len(files) - self.MAX_ROTATED_BACKUPS)
        for old in files[:cutoff]:
            old.unlink(missing_ok=True)

    def _atomic_write(self, data: dict[str, Any]) -> None:
        tmp_path = self.db_path.with_suffix(self.db_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self.db_path)
