"""供 Kotlin 调用的入口：JsonStorage + PortfolioService；与 Streamlit 共用 fundshare 逻辑。"""

from __future__ import annotations

import json
import os
from datetime import date
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


def _rpc(ok: bool, message: str = "", error: str = "", data: Any | None = None) -> str:
    payload: dict[str, Any] = {"ok": ok, "message": message, "error": error}
    if data is not None:
        payload["data"] = _json_safe(data)
    return json.dumps(payload, ensure_ascii=False)


def _fund_label(fund: dict[str, Any]) -> str:
    return f"{fund['code']} - {fund['name']} (NAV: {float(fund['current_nav']):.4f})"


def trades_payload_json(arg_json: str = "") -> str:
    """交易与净值页数据载荷（对齐 app.py/render_trades_and_chart）。"""
    _ensure_data_dir()
    from fundshare.errors import DomainError
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    args = json.loads(arg_json) if arg_json else {}
    svc = PortfolioService(JsonStorage())
    funds = svc.list_funds()
    if not funds:
        return json.dumps({"funds": [], "empty_reason": "请先在「基金管理」中新增基金。"}, ensure_ascii=False)

    selected_fund_id = int(args.get("fund_id") or funds[0]["id"])
    selected_fund = next((f for f in funds if int(f["id"]) == selected_fund_id), funds[0])
    fund_id = int(selected_fund["id"])
    date_field = "confirm_date"
    chart_range = str(args.get("chart_range") or "近1年")
    tx_type = str(args.get("tx_type") or "all")

    start_date = str(args.get("tx_start") or date.today().replace(day=1).isoformat())
    end_date = str(args.get("tx_end") or date.today().isoformat())

    summary = svc.get_position_summary(fund_id, date_field=date_field)
    remaining_shares = svc.get_remaining_shares(fund_id)
    sellable_lots = svc.get_sellable_buy_lots(fund_id, date_field=date_field)
    all_txs = svc.get_transactions(fund_id, date_field=date_field)

    if start_date <= end_date:
        filtered = svc.filter_transactions_by_date_range(
            fund_id,
            start_date,
            end_date,
            date_field=date_field,
        )
    else:
        filtered = all_txs

    filtered = svc.filter_transactions_by_type(filtered, tx_type=tx_type)

    tx_rows: list[dict[str, Any]] = []
    for tx in filtered:
        row = dict(tx)
        row["fund_id"] = fund_id
        row["fund_code"] = str(selected_fund["code"])
        row["fund_name"] = str(selected_fund["name"])
        tx_rows.append(row)
    tx_rows.sort(key=lambda x: (str(x["confirm_date"]), int(x["id"])), reverse=True)

    nav_points = svc.get_nav_points(fund_id)
    try:
        remote_nav = svc.api_client.fetch_nav_trend(str(selected_fund["code"]))
    except Exception:  # noqa: BLE001
        remote_nav = []
    if remote_nav:
        nav_points = remote_nav

    win_start, win_end = svc.nav_chart_date_window(nav_points, chart_range)
    nav_filtered = svc.filter_records_by_date_range(nav_points, "date", win_start, win_end)
    gaps = svc.nav_point_calendar_gaps(nav_filtered, min_gap_days=14)

    buy_lots_all = svc.buy_lot_rows_from_transactions(all_txs, date_field=date_field)
    buy_points_raw = [
        {
            "date": r["date"],
            "price": float(r["price"]),
            "original_shares": float(r["original_shares"]),
            "remaining_shares": float(r["remaining_shares"]),
        }
        for r in buy_lots_all
    ]
    buy_points_raw = svc.filter_records_by_date_range(buy_points_raw, "date", win_start, win_end)

    # 按日期聚合买入点（同网页逻辑）
    buy_points_by_date: dict[str, dict[str, Any]] = {}
    for p in buy_points_raw:
        d = str(p["date"])
        if d not in buy_points_by_date:
            buy_points_by_date[d] = {
                "date": d,
                "buy_count": 0,
                "original_shares": 0.0,
                "remaining_shares": 0.0,
                "weighted_cost": 0.0,
            }
        row = buy_points_by_date[d]
        row["buy_count"] += 1
        row["original_shares"] += float(p["original_shares"])
        row["remaining_shares"] += float(p["remaining_shares"])
        row["weighted_cost"] += float(p["price"]) * float(p["original_shares"])
    buy_points: list[dict[str, Any]] = []
    for d, row in sorted(buy_points_by_date.items(), key=lambda x: x[0]):
        orig = float(row["original_shares"])
        price = (float(row["weighted_cost"]) / orig) if orig > 1e-12 else 0.0
        buy_points.append(
            {
                "date": d,
                "price": price,
                "buy_count": int(row["buy_count"]),
                "original_shares": orig,
                "remaining_shares": float(row["remaining_shares"]),
            }
        )

    sell_points = [
        {"date": str(tx["confirm_date"]), "price": float(tx["price"]), "shares": float(tx["shares"])}
        for tx in all_txs
        if str(tx.get("tx_type")) == "sell"
    ]
    sell_points = svc.filter_records_by_date_range(sell_points, "date", win_start, win_end)

    warning = ""
    if start_date > end_date:
        warning = "开始日期不能晚于结束日期，将显示全部交易。"
    elif not filtered:
        warning = "当前筛选条件下暂无交易记录。"

    payload = {
        "funds": funds,
        "fund_options": [{"id": int(f["id"]), "label": _fund_label(f)} for f in funds],
        "selected_fund_id": fund_id,
        "selected_fund": selected_fund,
        "date_field": date_field,
        "chart_range": chart_range,
        "tx_type": tx_type,
        "tx_start": start_date,
        "tx_end": end_date,
        "summary": summary,
        "remaining_shares": remaining_shares,
        "sellable_lots": sellable_lots,
        "transactions": tx_rows,
        "nav_points": nav_filtered,
        "buy_points": buy_points,
        "sell_points": sell_points,
        "calendar_gaps": gaps,
        "chart_window": {"start": win_start, "end": win_end},
        "warning": warning,
    }
    return json.dumps(_json_safe(payload), ensure_ascii=False)


def trades_payload_json_safe(arg_json: str = "") -> str:
    try:
        return trades_payload_json(arg_json)
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {
                "funds": [],
                "transactions": [],
                "nav_points": [],
                "buy_points": [],
                "sell_points": [],
                "calendar_gaps": [],
                "warning": "",
                "error": str(e),
            },
            ensure_ascii=False,
        )


def trades_rpc(op: str, arg_json: str) -> str:
    """交易页操作 RPC：买卖、导入、导出 CSV。"""
    _ensure_data_dir()
    from fundshare.errors import DomainError
    from fundshare.service import PortfolioService
    from fundshare.storage import JsonStorage

    args = json.loads(arg_json) if arg_json else {}
    try:
        svc = PortfolioService(JsonStorage())
        if op == "add_buy":
            fund_id = int(args["fund_id"])
            confirm_date = str(args["confirm_date"]).strip()
            apply_date = str(args.get("apply_date") or confirm_date).strip()
            date.fromisoformat(confirm_date)
            date.fromisoformat(apply_date)
            price = float(args["price"])
            shares = float(args["shares"])
            fee = float(args.get("fee", 0.0))
            svc.add_buy(fund_id, apply_date, confirm_date, price, shares, fee)
            return _rpc(True, message="买入记录已保存。")

        if op == "add_sell_fifo":
            fund_id = int(args["fund_id"])
            confirm_date = str(args["confirm_date"]).strip()
            apply_date = str(args.get("apply_date") or confirm_date).strip()
            date.fromisoformat(confirm_date)
            date.fromisoformat(apply_date)
            price = float(args["price"])
            shares = float(args["shares"])
            fee = float(args.get("fee", 0.0))
            svc.add_sell(fund_id, apply_date, confirm_date, price, shares, fee)
            return _rpc(True, message="卖出记录已保存。")

        if op == "add_sell_by_lots":
            fund_id = int(args["fund_id"])
            confirm_date = str(args["confirm_date"]).strip()
            apply_date = str(args.get("apply_date") or confirm_date).strip()
            date.fromisoformat(confirm_date)
            date.fromisoformat(apply_date)
            price = float(args["price"])
            fee = float(args.get("fee", 0.0))
            picks = args.get("picks") or []
            if not isinstance(picks, list):
                return _rpc(False, error="picks 必须是数组")
            normalized_picks: list[dict[str, Any]] = []
            for row in picks:
                if not isinstance(row, dict):
                    return _rpc(False, error="picks 的每一项都必须是对象")
                buy_tx_id = int(row.get("buy_tx_id", 0))
                shares = float(row.get("shares", 0.0))
                if buy_tx_id <= 0 or shares <= 0.0:
                    return _rpc(False, error="picks 中包含无效 buy_tx_id 或 shares")
                normalized_picks.append({"buy_tx_id": buy_tx_id, "shares": shares})
            if not normalized_picks:
                return _rpc(False, error="请至少选择一个有效批次")
            svc.add_sell_by_lots(fund_id, apply_date, confirm_date, price, normalized_picks, fee)
            return _rpc(True, message="卖出记录已保存。")

        if op == "import_json":
            text = str(args.get("json_text", "")).strip()
            if not text:
                return _rpc(False, error="请先粘贴 JSON。")
            n = svc.import_transactions_json(text)
            return _rpc(True, message=f"已导入 {n} 条交易。")

        if op == "import_csv":
            csv_text = str(args.get("csv_text", "")).strip()
            fund_code = str(args.get("fund_code", "")).strip()
            if not csv_text:
                return _rpc(False, error="请先粘贴或上传 CSV。")
            if not fund_code:
                return _rpc(False, error="缺少 fund_code。")
            n = svc.import_transactions_csv(csv_text, fund_code)
            return _rpc(True, message=f"已导入 {n} 条交易。")

        if op == "export_csv":
            fund_id = int(args["fund_id"])
            csv_text = svc.export_transactions_csv(fund_id, date_field="confirm_date")
            return _rpc(True, message="导出成功。", data={"csv_text": csv_text})

        return _rpc(False, error=f"未知操作: {op}")
    except DomainError as e:
        return _rpc(False, error=str(e))
    except Exception as e:  # noqa: BLE001
        return _rpc(False, error=str(e))


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
