"""供 Kotlin 调用的入口：JsonStorage + PortfolioService；与 Streamlit 共用 fundshare 逻辑。"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any


def _ensure_data_dir() -> None:
    home = (os.environ.get("HOME") or "").strip()
    if home and not (os.environ.get("DATA_DIR") or "").strip():
        os.environ["DATA_DIR"] = home


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, (bool, str)) or obj is None:
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, float):
        return obj
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)


def get_status_line() -> str:
    """兼容旧版单屏；新 UI 请用 get_full_ui_payload_json。"""
    _ensure_data_dir()
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    svc = PortfolioService(JsonStorage())
    funds = svc.list_funds()
    ov = svc.get_portfolio_overview()
    data_dir = (os.environ.get("DATA_DIR") or "").strip()
    return (
        f"DATA_DIR={data_dir}\n"
        f"基金数量: {len(funds)}\n"
        f"组合总成本: {float(ov['total_cost']):.2f}\n"
        f"总市值: {float(ov['total_value']):.2f}"
    )


def get_full_ui_payload_json() -> str:
    """供 Android UI 一次拉取：与 app.py 中组合总览/表格同源数据（JSON 字符串）。"""
    _ensure_data_dir()
    from fundshare import __version__
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    svc = PortfolioService(JsonStorage())
    overview = _json_safe(svc.get_portfolio_overview())
    positions = _json_safe(svc.get_all_position_summaries())
    raw_funds = svc.list_funds()
    funds = _json_safe(raw_funds)

    txs_flat: list[dict[str, Any]] = []
    for f in raw_funds:
        fid = int(f["id"])
        for t in svc.get_transactions(fid):
            row = dict(t)
            row["fund_code"] = str(f["code"])
            row["fund_name"] = str(f["name"])
            txs_flat.append(_json_safe(row))
    txs_flat.sort(key=lambda x: str(x.get("confirm_date", "")), reverse=True)
    txs_flat = txs_flat[:120]

    payload = {
        "fundshare_version": __version__,
        "data_dir": (os.environ.get("DATA_DIR") or "").strip(),
        "overview": overview,
        "positions": positions,
        "funds": funds,
        "transactions": txs_flat,
        "error": None,
    }
    return json.dumps(payload, ensure_ascii=False)


def get_full_ui_payload_json_safe() -> str:
    """Kotlin 侧优先调用：异常时仍返回可解析 JSON，便于界面展示错误。"""
    try:
        return get_full_ui_payload_json()
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {
                "fundshare_version": "",
                "data_dir": "",
                "overview": {},
                "positions": [],
                "funds": [],
                "transactions": [],
                "error": str(e),
            },
            ensure_ascii=False,
        )
