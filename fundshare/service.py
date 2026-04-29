from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta
from io import StringIO
import re
from typing import Any

from .errors import DomainError
from .fund_api import FundApiClient
from .models import Fund, NavPoint, Transaction
from .money import q_money, q_ratio
from .storage import JsonStorage


def _normalize_csv_header(name: str | None) -> str:
    if name is None:
        return ""
    return str(name).strip().lower().lstrip("\ufeff")


class PortfolioService:
    def __init__(self, storage: JsonStorage | None = None, api_client: FundApiClient | None = None) -> None:
        self.storage = storage or JsonStorage()
        self.api_client = api_client or FundApiClient()

    def _load(self) -> dict[str, Any]:
        return self.storage.load()

    def _save(self, data: dict[str, Any]) -> None:
        self.storage.save(data)

    def _next_id(self, data: dict[str, Any], key: str) -> int:
        current = data["next_ids"][key]
        data["next_ids"][key] += 1
        return current

    def list_funds(self) -> list[dict[str, Any]]:
        data = self._load()
        return data["funds"]

    def delete_fund(self, fund_id: int) -> None:
        data = self._load()
        self._ensure_fund(data, fund_id)
        if self._total_remaining_shares(data, fund_id) > 1e-9:
            raise DomainError("尚有持仓份额，无法删除基金")
        data["funds"] = [f for f in data["funds"] if f["id"] != fund_id]
        data["nav_points"] = [p for p in data["nav_points"] if p["fund_id"] != fund_id]
        data["transactions"] = [t for t in data["transactions"] if t["fund_id"] != fund_id]
        self._save(data)

    def clear_fund_records(self, fund_id: int) -> None:
        data = self._load()
        self._ensure_fund(data, fund_id)
        data["nav_points"] = [p for p in data["nav_points"] if p["fund_id"] != fund_id]
        data["transactions"] = [t for t in data["transactions"] if t["fund_id"] != fund_id]
        self._save(data)

    def purge_fund(self, fund_id: int) -> None:
        data = self._load()
        self._ensure_fund(data, fund_id)
        data["funds"] = [f for f in data["funds"] if f["id"] != fund_id]
        data["nav_points"] = [p for p in data["nav_points"] if p["fund_id"] != fund_id]
        data["transactions"] = [t for t in data["transactions"] if t["fund_id"] != fund_id]
        self._save(data)

    def delete_transaction(self, fund_id: int, tx_id: int) -> None:
        data = self._load()
        self._ensure_fund(data, fund_id)
        txs = data["transactions"]
        idx = next((i for i, t in enumerate(txs) if t["fund_id"] == fund_id and int(t["id"]) == int(tx_id)), -1)
        if idx < 0:
            raise DomainError("交易记录不存在")
        txs.pop(idx)
        self._ensure_trade_sequence_valid(data, fund_id)
        self._save(data)

    def add_fund(self, code: str, name: str, current_nav: float, nav_date: str | None = None) -> dict[str, Any]:
        data = self._load()
        normalized_code = self.normalize_fund_code(code)
        if any(f["code"] == normalized_code for f in data["funds"]):
            raise DomainError("基金代码已存在，请勿重复添加")
        if float(current_nav) <= 0:
            raise DomainError("基金净值必须大于0")
        fund = Fund(
            id=self._next_id(data, "fund"),
            code=normalized_code,
            name=name.strip(),
            current_nav=float(current_nav),
        ).to_dict()
        data["funds"].append(fund)
        point = NavPoint(
            id=self._next_id(data, "nav"),
            fund_id=fund["id"],
            date=nav_date or date.today().isoformat(),
            nav=float(current_nav),
        ).to_dict()
        data["nav_points"].append(point)
        self._save(data)
        return fund

    def update_fund_nav(self, fund_id: int, nav: float, nav_date: str | None = None) -> None:
        data = self._load()
        if float(nav) <= 0:
            raise DomainError("基金净值必须大于0")
        for fund in data["funds"]:
            if fund["id"] == fund_id:
                fund["current_nav"] = float(nav)
                break
        else:
            raise DomainError("基金不存在")
        data["nav_points"].append(
            NavPoint(
                id=self._next_id(data, "nav"),
                fund_id=fund_id,
                date=nav_date or date.today().isoformat(),
                nav=float(nav),
            ).to_dict()
        )
        self._save(data)

    def add_buy(
        self,
        fund_id: int,
        apply_date: str,
        confirm_date: str,
        price: float,
        shares: float,
        fee: float = 0.0,
    ) -> dict[str, Any]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        self._validate_trade_inputs(apply_date, confirm_date, price, shares, fee)
        tx = Transaction(
            id=self._next_id(data, "tx"),
            fund_id=fund_id,
            tx_type="buy",
            apply_date=apply_date,
            confirm_date=confirm_date,
            price=float(price),
            shares=float(shares),
            amount=q_money(float(price) * float(shares)),
            fee=q_money(float(fee)),
            allocations=[],
        ).to_dict()
        data["transactions"].append(tx)
        self._save(data)
        return tx

    def add_sell(
        self,
        fund_id: int,
        apply_date: str,
        confirm_date: str,
        price: float,
        shares: float,
        fee: float = 0.0,
    ) -> dict[str, Any]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        self._validate_trade_inputs(apply_date, confirm_date, price, shares, fee)
        sell_shares = float(shares)
        remain = self._total_remaining_shares(data, fund_id)
        if sell_shares > remain + 1e-9:
            raise DomainError("卖出份额超过当前持仓")
        allocations = self._build_fifo_allocations(data, fund_id, sell_shares)
        tx = Transaction(
            id=self._next_id(data, "tx"),
            fund_id=fund_id,
            tx_type="sell",
            apply_date=apply_date,
            confirm_date=confirm_date,
            price=float(price),
            shares=sell_shares,
            amount=q_money(float(price) * sell_shares),
            fee=q_money(float(fee)),
            allocations=allocations,
        ).to_dict()
        data["transactions"].append(tx)
        self._save(data)
        return tx

    def add_sell_by_lots(
        self,
        fund_id: int,
        apply_date: str,
        confirm_date: str,
        price: float,
        picks: list[dict[str, Any]],
        fee: float = 0.0,
    ) -> dict[str, Any]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        if not picks:
            raise DomainError("请至少选择一条买入批次")
        lots = self._build_lot_states(data, fund_id, date_field="confirm_date")
        open_map = {int(l["buy_id"]): float(l["remaining_shares"]) for l in lots if float(l["remaining_shares"]) > 1e-9}
        allocations: list[dict[str, float]] = []
        total_shares = 0.0
        seen_ids: set[int] = set()
        for p in picks:
            try:
                buy_tx_id = int(p["buy_tx_id"])
                sh = float(p["shares"])
            except (KeyError, TypeError, ValueError) as e:
                raise DomainError(f"批次选择格式错误: {p}") from e
            if sh <= 0:
                raise DomainError("批次卖出份额必须大于0")
            if buy_tx_id in seen_ids:
                raise DomainError("同一买入批次请只填写一次")
            seen_ids.add(buy_tx_id)
            remain = open_map.get(buy_tx_id)
            if remain is None:
                raise DomainError(f"买入批次不存在或已无剩余份额: {buy_tx_id}")
            if sh > remain + 1e-9:
                raise DomainError(f"批次 {buy_tx_id} 卖出份额超过可用剩余 {remain:.4f}")
            allocations.append({"buy_tx_id": buy_tx_id, "shares": q_money(sh)})
            total_shares += sh
        self._validate_trade_inputs(apply_date, confirm_date, price, total_shares, fee)
        tx = Transaction(
            id=self._next_id(data, "tx"),
            fund_id=fund_id,
            tx_type="sell",
            apply_date=apply_date,
            confirm_date=confirm_date,
            price=float(price),
            shares=q_money(total_shares),
            amount=q_money(float(price) * total_shares),
            fee=q_money(float(fee)),
            allocations=allocations,
        ).to_dict()
        data["transactions"].append(tx)
        self._save(data)
        return tx

    def get_nav_points(self, fund_id: int) -> list[dict[str, Any]]:
        data = self._load()
        points = [p for p in data["nav_points"] if p["fund_id"] == fund_id]
        return sorted(points, key=lambda x: x["date"])

    def get_transactions(self, fund_id: int, date_field: str = "confirm_date") -> list[dict[str, Any]]:
        data = self._load()
        txs = [tx for tx in data["transactions"] if tx["fund_id"] == fund_id]
        if date_field not in {"confirm_date", "apply_date"}:
            raise DomainError("date_field must be confirm_date or apply_date")
        return sorted(txs, key=lambda x: (x[date_field], x["id"]))

    def filter_transactions_by_date_range(
        self,
        fund_id: int,
        start_date: str,
        end_date: str,
        date_field: str = "confirm_date",
    ) -> list[dict[str, Any]]:
        if start_date > end_date:
            raise DomainError("开始日期不能晚于结束日期")
        txs = self.get_transactions(fund_id, date_field=date_field)
        return [tx for tx in txs if start_date <= tx[date_field] <= end_date]

    @staticmethod
    def filter_transactions_by_type(
        transactions: list[dict[str, Any]], tx_type: str = "all"
    ) -> list[dict[str, Any]]:
        if tx_type == "all":
            return transactions
        if tx_type not in {"buy", "sell"}:
            raise DomainError("tx_type must be all, buy or sell")
        return [tx for tx in transactions if tx["tx_type"] == tx_type]

    def get_open_buy_points(self, fund_id: int, date_field: str = "confirm_date") -> list[dict[str, Any]]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        lots = self._build_lot_states(data, fund_id, date_field=date_field)
        return [lot for lot in lots if float(lot["remaining_shares"]) > 1e-9]

    def get_sellable_buy_lots(self, fund_id: int, date_field: str = "confirm_date") -> list[dict[str, Any]]:
        return self.get_open_buy_points(fund_id, date_field=date_field)

    @staticmethod
    def _holding_days_for_open_lots(
        open_lots: list[dict[str, Any]], as_of: date
    ) -> tuple[float, float]:
        """Shares-weighted average days held for open lots, and days since earliest open lot date."""
        total_sh = sum(float(lot["remaining_shares"]) for lot in open_lots)
        if total_sh <= 1e-9:
            return 0.0, 0.0
        weighted = 0.0
        earliest: date | None = None
        for lot in open_lots:
            d0 = datetime.strptime(str(lot["date"]), "%Y-%m-%d").date()
            days = max(0, (as_of - d0).days)
            weighted += float(lot["remaining_shares"]) * float(days)
            if earliest is None or d0 < earliest:
                earliest = d0
        first_age = max(0, (as_of - earliest).days) if earliest is not None else 0
        return weighted / total_sh, float(first_age)

    def _ensure_fund(self, data: dict[str, Any], fund_id: int) -> None:
        if not any(f["id"] == fund_id for f in data["funds"]):
            raise DomainError("基金不存在")

    def _total_remaining_shares(self, data: dict[str, Any], fund_id: int) -> float:
        bought = sum(tx["shares"] for tx in data["transactions"] if tx["fund_id"] == fund_id and tx["tx_type"] == "buy")
        sold = sum(tx["shares"] for tx in data["transactions"] if tx["fund_id"] == fund_id and tx["tx_type"] == "sell")
        return float(bought - sold)

    @staticmethod
    def _ensure_trade_sequence_valid(data: dict[str, Any], fund_id: int, eps: float = 1e-9) -> None:
        txs = [tx for tx in data["transactions"] if tx["fund_id"] == fund_id]
        txs.sort(key=lambda x: (x["confirm_date"], int(x["id"])))
        balance = 0.0
        for tx in txs:
            sh = float(tx["shares"])
            if tx["tx_type"] == "buy":
                balance += sh
            else:
                balance -= sh
            if balance < -eps:
                raise DomainError("删除后交易序列非法：历史卖出累计超过买入累计")

    def _build_fifo_allocations(self, data: dict[str, Any], fund_id: int, sell_shares: float) -> list[dict[str, float]]:
        lots = self._build_lot_states(data, fund_id, date_field="confirm_date")
        remaining = float(sell_shares)
        allocations: list[dict[str, float]] = []
        for lot in lots:
            rem = float(lot["remaining_shares"])
            if rem <= 1e-9:
                continue
            if remaining <= 1e-9:
                break
            consumed = min(rem, remaining)
            allocations.append({"buy_tx_id": int(lot["buy_id"]), "shares": q_money(consumed)})
            remaining -= consumed
        if remaining > 1e-9:
            raise DomainError("卖出份额超过当前持仓")
        return allocations

    def _build_lot_states(self, data: dict[str, Any], fund_id: int, date_field: str = "confirm_date") -> list[dict[str, Any]]:
        txs = [tx for tx in data["transactions"] if tx["fund_id"] == fund_id]
        txs.sort(key=lambda x: (x[date_field], int(x["id"])))
        lots: list[dict[str, Any]] = []
        for tx in txs:
            if tx["tx_type"] == "buy":
                lots.append(
                    {
                        "buy_id": int(tx["id"]),
                        "date": tx[date_field],
                        "price": float(tx["price"]),
                        "original_shares": float(tx["shares"]),
                        "remaining_shares": float(tx["shares"]),
                    }
                )
                continue
            allocations = tx.get("allocations") or []
            if allocations:
                lot_map = {int(l["buy_id"]): l for l in lots}
                for a in allocations:
                    try:
                        buy_tx_id = int(a["buy_tx_id"])
                        sh = float(a["shares"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    lot = lot_map.get(buy_tx_id)
                    if lot is not None:
                        lot["remaining_shares"] -= sh
            else:
                remaining_sell = float(tx["shares"])
                for lot in lots:
                    if remaining_sell <= 1e-9:
                        break
                    if float(lot["remaining_shares"]) <= 1e-9:
                        continue
                    consumed = min(float(lot["remaining_shares"]), remaining_sell)
                    lot["remaining_shares"] -= consumed
                    remaining_sell -= consumed
        return lots

    def get_remaining_shares(self, fund_id: int) -> float:
        data = self._load()
        self._ensure_fund(data, fund_id)
        return q_money(self._total_remaining_shares(data, fund_id))

    def auto_fetch_fund_info(self, code: str, target_date: str) -> tuple[str, float]:
        return self.api_client.fetch_name_and_nav(self.normalize_fund_code(code), target_date)

    @staticmethod
    def normalize_fund_code(code: str) -> str:
        normalized = code.strip()
        if not normalized:
            raise DomainError("基金代码不能为空")
        if not re.fullmatch(r"\d{6}", normalized):
            raise DomainError("基金代码格式错误，应为6位数字")
        return normalized

    def export_transactions_csv(self, fund_id: int, date_field: str = "confirm_date") -> str:
        txs = self.get_transactions(fund_id, date_field=date_field)
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["tx_type", "apply_date", "confirm_date", "price", "shares", "amount", "fee", "allocations_json"])
        for tx in txs:
            w.writerow(
                [
                    tx["tx_type"],
                    tx["apply_date"],
                    tx["confirm_date"],
                    tx["price"],
                    tx["shares"],
                    tx["amount"],
                    tx.get("fee", 0.0),
                    json.dumps(tx.get("allocations", []), ensure_ascii=False),
                ]
            )
        return buf.getvalue()

    def get_position_summary(self, fund_id: int, date_field: str = "confirm_date") -> dict[str, Any]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        if date_field not in {"confirm_date", "apply_date"}:
            raise DomainError("date_field must be confirm_date or apply_date")
        fund = next(f for f in data["funds"] if f["id"] == fund_id)
        open_lots = self.get_open_buy_points(fund_id, date_field=date_field)
        holding_shares = sum(lot["remaining_shares"] for lot in open_lots)
        holding_cost = sum(lot["remaining_shares"] * lot["price"] for lot in open_lots)
        market_value = holding_shares * float(fund["current_nav"])
        floating_pnl = market_value - holding_cost
        avg_cost = (holding_cost / holding_shares) if holding_shares > 0 else 0.0
        avg_days, first_lot_days = self._holding_days_for_open_lots(open_lots, date.today())
        avg_days_r = round(avg_days, 1)
        first_lot_r = round(first_lot_days, 1)
        if holding_cost > 1e-9 and avg_days > 1e-9:
            annual_simple = q_ratio((floating_pnl / holding_cost) * (365.0 / avg_days))
        else:
            annual_simple = 0.0
        return {
            "holding_shares": q_money(holding_shares),
            "holding_cost": q_money(holding_cost),
            "avg_cost": q_money(avg_cost),
            "market_value": q_money(market_value),
            "floating_pnl": q_money(floating_pnl),
            "current_nav": q_money(float(fund["current_nav"])),
            "avg_holding_days": avg_days_r,
            "first_lot_age_days": first_lot_r,
            "annualized_simple_ratio": annual_simple,
        }

    def get_all_position_summaries(self, date_field: str = "confirm_date") -> list[dict[str, Any]]:
        funds = self.list_funds()
        summaries: list[dict[str, Any]] = []
        for fund in funds:
            summary = self.get_position_summary(fund["id"], date_field=date_field)
            summaries.append(
                {
                    "fund_id": fund["id"],
                    "code": fund["code"],
                    "name": fund["name"],
                    **summary,
                }
            )
        return sorted(summaries, key=lambda x: x["floating_pnl"], reverse=True)

    def export_portfolio_csv(self) -> str:
        rows = self.get_all_position_summaries()
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "code",
                "name",
                "holding_shares",
                "holding_cost",
                "avg_cost",
                "current_nav",
                "market_value",
                "floating_pnl",
                "pnl_ratio",
                "avg_holding_days",
                "first_lot_age_days",
                "annualized_simple_ratio",
            ]
        )
        for r in rows:
            cost = float(r["holding_cost"])
            pnl = float(r["floating_pnl"])
            ratio = q_ratio((pnl / cost) if cost > 0 else 0.0)
            w.writerow(
                [
                    r["code"],
                    r["name"],
                    r["holding_shares"],
                    r["holding_cost"],
                    r["avg_cost"],
                    r["current_nav"],
                    r["market_value"],
                    r["floating_pnl"],
                    ratio,
                    r["avg_holding_days"],
                    r["first_lot_age_days"],
                    r["annualized_simple_ratio"],
                ]
            )
        return buf.getvalue()

    @staticmethod
    def _parse_import_tx_row(row: dict[str, Any]) -> tuple[str, str, str, float, float, float]:
        try:
            tx_type = str(row["tx_type"]).strip().lower()
            apply_date = str(row["apply_date"]).strip()
            confirm_date = str(row["confirm_date"]).strip()
            price = float(row["price"])
            shares = float(row["shares"])
            raw_fee = row.get("fee")
            if raw_fee is None or (isinstance(raw_fee, str) and not str(raw_fee).strip()):
                fee = 0.0
            else:
                fee = float(raw_fee)
        except (KeyError, TypeError, ValueError) as e:
            raise DomainError(f"交易记录字段不完整或类型错误: {e}") from e
        if tx_type not in ("buy", "sell"):
            raise DomainError("tx_type 必须是 buy 或 sell")
        datetime.strptime(apply_date, "%Y-%m-%d")
        datetime.strptime(confirm_date, "%Y-%m-%d")
        if fee < 0:
            raise DomainError("手续费不能为负数")
        return tx_type, apply_date, confirm_date, price, shares, fee

    def import_transactions_json(self, json_text: str) -> int:
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise DomainError(f"JSON 解析失败: {e}") from e
        if not isinstance(payload, dict):
            raise DomainError("JSON 根节点必须是对象")
        fund_code_raw = payload.get("fund_code")
        if not fund_code_raw:
            raise DomainError("缺少 fund_code")
        rows = payload.get("transactions")
        if not isinstance(rows, list) or not rows:
            raise DomainError("transactions 必须是非空数组")
        data = self._load()
        normalized = self.normalize_fund_code(str(fund_code_raw))
        fund = next((f for f in data["funds"] if f["code"] == normalized), None)
        if not fund:
            raise DomainError("基金不存在，请先添加该基金")
        fund_id = int(fund["id"])
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                raise DomainError("transactions 中每项必须是对象")
            tx_type, apply_date, confirm_date, price, shares, fee = self._parse_import_tx_row(row)
            allocs = self._parse_import_allocations(row.get("allocations"))
            if tx_type == "buy":
                self.add_buy(fund_id, apply_date, confirm_date, price, shares, fee)
            else:
                if allocs:
                    self.add_sell_by_lots(fund_id, apply_date, confirm_date, price, allocs, fee)
                else:
                    self.add_sell(fund_id, apply_date, confirm_date, price, shares, fee)
            count += 1
        return count

    def import_transactions_csv(self, csv_text: str, fund_code: str) -> int:
        data = self._load()
        normalized = self.normalize_fund_code(str(fund_code).strip())
        fund = next((f for f in data["funds"] if f["code"] == normalized), None)
        if not fund:
            raise DomainError("基金不存在，请先添加该基金")
        fund_id = int(fund["id"])
        stream = StringIO(csv_text.strip())
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise DomainError("CSV 无表头或内容为空")
        required = {"tx_type", "apply_date", "confirm_date", "price", "shares"}
        rows_iter = list(reader)
        if not rows_iter:
            raise DomainError("CSV 无数据行")
        first_keys = {_normalize_csv_header(h) for h in reader.fieldnames if h is not None and str(h).strip()}
        missing = required - first_keys
        if missing:
            raise DomainError(f"CSV 缺少列: {', '.join(sorted(missing))}")
        count = 0
        for raw in rows_iter:
            row: dict[str, Any] = {}
            for k, v in raw.items():
                if k is None:
                    continue
                nk = _normalize_csv_header(k)
                if not nk:
                    continue
                row[nk] = v.strip() if isinstance(v, str) else v
            if not any(str(row.get(c, "") or "").strip() for c in required):
                continue
            tx_type, apply_date, confirm_date, price, shares, fee = self._parse_import_tx_row(row)
            allocs = self._parse_import_allocations_csv_cell(row.get("allocations_json"))
            exp_amt = q_money(float(price) * float(shares))
            amt_raw = row.get("amount")
            if amt_raw is not None and str(amt_raw).strip() != "":
                try:
                    amtv = float(str(amt_raw).strip())
                except (TypeError, ValueError) as e:
                    raise DomainError(f"CSV amount 列无法解析为数字: {amt_raw}") from e
                if abs(amtv - exp_amt) > 0.02:
                    raise DomainError(f"CSV 金额与价格×份额不符: amount={amtv} 期望≈{exp_amt}")
            if tx_type == "buy":
                self.add_buy(fund_id, apply_date, confirm_date, price, shares, fee)
            else:
                if allocs:
                    self.add_sell_by_lots(fund_id, apply_date, confirm_date, price, allocs, fee)
                else:
                    self.add_sell(fund_id, apply_date, confirm_date, price, shares, fee)
            count += 1
        if count == 0:
            raise DomainError("未导入任何有效交易行")
        return count

    @staticmethod
    def _parse_import_allocations(raw: Any) -> list[dict[str, float]]:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise DomainError("allocations 必须是数组")
        out: list[dict[str, float]] = []
        for it in raw:
            if not isinstance(it, dict):
                raise DomainError("allocations 中每项必须是对象")
            try:
                buy_tx_id = int(it["buy_tx_id"])
                shares = float(it["shares"])
            except (KeyError, TypeError, ValueError) as e:
                raise DomainError(f"allocations 字段错误: {it}") from e
            if shares <= 0:
                raise DomainError("allocations 中 shares 必须大于0")
            out.append({"buy_tx_id": buy_tx_id, "shares": shares})
        return out

    def _parse_import_allocations_csv_cell(self, raw: Any) -> list[dict[str, float]]:
        if raw is None or str(raw).strip() == "":
            return []
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError as e:
            raise DomainError(f"allocations_json 解析失败: {e}") from e
        return self._parse_import_allocations(payload)

    def get_portfolio_overview(self) -> dict[str, float]:
        rows = self.get_all_position_summaries()
        total_cost = sum(float(r["holding_cost"]) for r in rows)
        total_value = sum(float(r["market_value"]) for r in rows)
        total_pnl = total_value - total_cost
        pnl_ratio = (total_pnl / total_cost) if total_cost > 0 else 0.0
        data = self._load()
        buy_amount = sum(
            float(tx["amount"]) for tx in data["transactions"] if tx["tx_type"] == "buy"
        )
        sell_amount = sum(
            float(tx["amount"]) for tx in data["transactions"] if tx["tx_type"] == "sell"
        )
        total_fees = sum(float(tx.get("fee", 0.0)) for tx in data["transactions"])
        realized_pnl = sell_amount - buy_amount + total_cost
        return {
            "total_cost": q_money(total_cost),
            "total_value": q_money(total_value),
            "total_pnl": q_money(total_pnl),
            "pnl_ratio": q_ratio(pnl_ratio),
            "buy_amount": q_money(buy_amount),
            "sell_amount": q_money(sell_amount),
            "realized_pnl": q_money(realized_pnl),
            "total_fees": q_money(total_fees),
            "realized_pnl_after_fees": q_money(realized_pnl - total_fees),
        }

    @staticmethod
    def _validate_trade_inputs(
        apply_date: str, confirm_date: str, price: float, shares: float, fee: float = 0.0
    ) -> None:
        if apply_date > confirm_date:
            raise DomainError("申请日不能晚于确认日")
        if float(price) <= 0:
            raise DomainError("价格必须大于0")
        if float(shares) <= 0:
            raise DomainError("份额必须大于0")
        if float(fee) < 0:
            raise DomainError("手续费不能为负数")

    @staticmethod
    def classify_sell_risk(
        remaining_shares: float,
        sell_shares: float,
        *,
        large_ratio: float = 0.5,
        eps: float = 1e-9,
    ) -> str:
        """Return none | large | clearout. Assumes sell_shares <= remaining (UI enforces max)."""
        if remaining_shares <= eps or sell_shares <= eps:
            return "none"
        if sell_shares + eps >= remaining_shares:
            return "clearout"
        if sell_shares + eps >= remaining_shares * large_ratio:
            return "large"
        return "none"

    @staticmethod
    def filter_records_by_date_range(
        records: list[dict[str, Any]],
        date_key: str,
        start_iso: str | None,
        end_iso: str | None,
    ) -> list[dict[str, Any]]:
        out = records
        if start_iso is not None:
            out = [r for r in out if r[date_key] >= start_iso]
        if end_iso is not None:
            out = [r for r in out if r[date_key] <= end_iso]
        return out

    @staticmethod
    def nav_chart_date_window(
        nav_points: list[dict[str, Any]], preset: str
    ) -> tuple[str | None, str | None]:
        """preset: 全部 | 近1月 | 近3月 | 近1年. Returns (start_iso, end_iso) inclusive; None means unbounded."""
        if not nav_points or preset == "全部":
            return None, None
        dates = sorted(p["date"] for p in nav_points)
        end = dates[-1]
        end_d = datetime.strptime(end, "%Y-%m-%d").date()
        days = {"近1月": 30, "近3月": 90, "近1年": 365}.get(preset, 0)
        if days <= 0:
            return None, None
        start_d = end_d - timedelta(days=days)
        return start_d.isoformat(), end

    @staticmethod
    def nav_point_calendar_gaps(
        nav_points: list[dict[str, Any]],
        *,
        min_gap_days: int = 14,
    ) -> list[tuple[str, str, int]]:
        """Consecutive trading-date gaps (calendar days) between sorted nav point dates, if gap > min_gap_days."""
        if len(nav_points) < 2:
            return []
        dates = sorted(datetime.strptime(p["date"], "%Y-%m-%d").date() for p in nav_points)
        gaps: list[tuple[str, str, int]] = []
        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i - 1]).days
            if delta > min_gap_days:
                gaps.append((dates[i - 1].isoformat(), dates[i].isoformat(), delta))
        return gaps

