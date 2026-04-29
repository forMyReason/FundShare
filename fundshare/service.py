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
        self, fund_id: int, apply_date: str, confirm_date: str, price: float, shares: float
    ) -> dict[str, Any]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        self._validate_trade_inputs(apply_date, confirm_date, price, shares)
        tx = Transaction(
            id=self._next_id(data, "tx"),
            fund_id=fund_id,
            tx_type="buy",
            apply_date=apply_date,
            confirm_date=confirm_date,
            price=float(price),
            shares=float(shares),
            amount=q_money(float(price) * float(shares)),
        ).to_dict()
        data["transactions"].append(tx)
        self._save(data)
        return tx

    def add_sell(
        self, fund_id: int, apply_date: str, confirm_date: str, price: float, shares: float
    ) -> dict[str, Any]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        self._validate_trade_inputs(apply_date, confirm_date, price, shares)
        sell_shares = float(shares)
        remain = self._total_remaining_shares(data, fund_id)
        if sell_shares > remain + 1e-9:
            raise DomainError("卖出份额超过当前持仓")
        tx = Transaction(
            id=self._next_id(data, "tx"),
            fund_id=fund_id,
            tx_type="sell",
            apply_date=apply_date,
            confirm_date=confirm_date,
            price=float(price),
            shares=sell_shares,
            amount=q_money(float(price) * sell_shares),
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
        buys = self.get_transactions(fund_id, date_field=date_field)
        lots: list[dict[str, Any]] = []
        for tx in buys:
            if tx["tx_type"] == "buy":
                lots.append(
                    {
                        "buy_id": tx["id"],
                        "date": tx[date_field],
                        "price": tx["price"],
                        "original_shares": tx["shares"],
                        "remaining_shares": tx["shares"],
                    }
                )
            else:
                remaining_sell = tx["shares"]
                for lot in lots:
                    if remaining_sell <= 0:
                        break
                    if lot["remaining_shares"] <= 0:
                        continue
                    consumed = min(lot["remaining_shares"], remaining_sell)
                    lot["remaining_shares"] -= consumed
                    remaining_sell -= consumed
        return [lot for lot in lots if lot["remaining_shares"] > 1e-9]

    def _ensure_fund(self, data: dict[str, Any], fund_id: int) -> None:
        if not any(f["id"] == fund_id for f in data["funds"]):
            raise DomainError("基金不存在")

    def _total_remaining_shares(self, data: dict[str, Any], fund_id: int) -> float:
        bought = sum(tx["shares"] for tx in data["transactions"] if tx["fund_id"] == fund_id and tx["tx_type"] == "buy")
        sold = sum(tx["shares"] for tx in data["transactions"] if tx["fund_id"] == fund_id and tx["tx_type"] == "sell")
        return float(bought - sold)

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
        output = StringIO()
        output.write("tx_type,apply_date,confirm_date,price,shares,amount\n")
        for tx in txs:
            output.write(
                f"{tx['tx_type']},{tx['apply_date']},{tx['confirm_date']},{tx['price']},{tx['shares']},{tx['amount']}\n"
            )
        return output.getvalue()

    def get_position_summary(self, fund_id: int) -> dict[str, float]:
        data = self._load()
        self._ensure_fund(data, fund_id)
        fund = next(f for f in data["funds"] if f["id"] == fund_id)
        open_lots = self.get_open_buy_points(fund_id, date_field="confirm_date")
        holding_shares = sum(lot["remaining_shares"] for lot in open_lots)
        holding_cost = sum(lot["remaining_shares"] * lot["price"] for lot in open_lots)
        market_value = holding_shares * float(fund["current_nav"])
        floating_pnl = market_value - holding_cost
        avg_cost = (holding_cost / holding_shares) if holding_shares > 0 else 0.0
        return {
            "holding_shares": q_money(holding_shares),
            "holding_cost": q_money(holding_cost),
            "avg_cost": q_money(avg_cost),
            "market_value": q_money(market_value),
            "floating_pnl": q_money(floating_pnl),
            "current_nav": q_money(float(fund["current_nav"])),
        }

    def get_all_position_summaries(self) -> list[dict[str, Any]]:
        funds = self.list_funds()
        summaries: list[dict[str, Any]] = []
        for fund in funds:
            summary = self.get_position_summary(fund["id"])
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
                ]
            )
        return buf.getvalue()

    @staticmethod
    def _parse_import_tx_row(row: dict[str, Any]) -> tuple[str, str, str, float, float]:
        try:
            tx_type = str(row["tx_type"]).strip().lower()
            apply_date = str(row["apply_date"]).strip()
            confirm_date = str(row["confirm_date"]).strip()
            price = float(row["price"])
            shares = float(row["shares"])
        except (KeyError, TypeError, ValueError) as e:
            raise DomainError(f"交易记录字段不完整或类型错误: {e}") from e
        if tx_type not in ("buy", "sell"):
            raise DomainError("tx_type 必须是 buy 或 sell")
        datetime.strptime(apply_date, "%Y-%m-%d")
        datetime.strptime(confirm_date, "%Y-%m-%d")
        return tx_type, apply_date, confirm_date, price, shares

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
            tx_type, apply_date, confirm_date, price, shares = self._parse_import_tx_row(row)
            if tx_type == "buy":
                self.add_buy(fund_id, apply_date, confirm_date, price, shares)
            else:
                self.add_sell(fund_id, apply_date, confirm_date, price, shares)
            count += 1
        return count

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
        realized_pnl = sell_amount - buy_amount + total_cost
        return {
            "total_cost": q_money(total_cost),
            "total_value": q_money(total_value),
            "total_pnl": q_money(total_pnl),
            "pnl_ratio": q_ratio(pnl_ratio),
            "buy_amount": q_money(buy_amount),
            "sell_amount": q_money(sell_amount),
            "realized_pnl": q_money(realized_pnl),
        }

    @staticmethod
    def _validate_trade_inputs(apply_date: str, confirm_date: str, price: float, shares: float) -> None:
        if apply_date > confirm_date:
            raise DomainError("申请日不能晚于确认日")
        if float(price) <= 0:
            raise DomainError("价格必须大于0")
        if float(shares) <= 0:
            raise DomainError("份额必须大于0")

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

