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
            row["fund_id"] = fid
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


def _rpc(ok: bool, message: str = "", error: str = "") -> str:
    return json.dumps({"ok": ok, "message": message, "error": error}, ensure_ascii=False)


def maintenance_rpc(op: str, arg_json: str) -> str:
    """与 Streamlit render_maintenance 同源操作：add_fund | delete_fund | clear_records | purge_fund | delete_tx。"""
    _ensure_data_dir()
    from datetime import date

    from fundshare.errors import DomainError
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    args = json.loads(arg_json) if arg_json else {}

    try:
        svc = PortfolioService(JsonStorage())
        if op == "add_fund":
            code = str(args.get("code", "")).strip()
            if not code:
                return _rpc(False, error="基金代码不能为空")
            name, nav = svc.auto_fetch_fund_info(code, date.today().isoformat())
            svc.add_fund(code, name, nav, date.today().isoformat())
            return _rpc(True, message=f"基金已新增：{name}，当前净值 {float(nav):.4f}")

        fund_id = int(args["fund_id"])

        if op == "delete_fund":
            svc.delete_fund(fund_id)
            return _rpc(True, message="已删除该基金及其历史净值与交易。")

        if op == "clear_records":
            svc.clear_fund_records(fund_id)
            return _rpc(True, message="该基金历史记录已清空。")

        if op == "purge_fund":
            phrase = str(args.get("phrase", "")).strip().upper()
            if phrase != "DELETE":
                return _rpc(False, error="确认词不正确，请输入 DELETE")
            svc.purge_fund(fund_id)
            return _rpc(True, message="基金及其所有记录已删除。")

        if op == "delete_tx":
            tx_id = int(args["tx_id"])
            svc.delete_transaction(fund_id, tx_id)
            return _rpc(True, message="交易记录已删除。")

        return _rpc(False, error=f"未知操作: {op}")
    except DomainError as e:
        return _rpc(False, error=str(e))
    except Exception as e:  # noqa: BLE001
        return _rpc(False, error=str(e))
