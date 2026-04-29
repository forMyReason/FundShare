from __future__ import annotations

from datetime import date
from io import StringIO
from typing import Any

from .fund_api import FundApiClient
from .models import Fund, NavPoint, Transaction
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

    def add_fund(self, code: str, name: str, current_nav: float, nav_date: str | None = None) -> dict[str, Any]:
        data = self._load()
        normalized_code = code.strip()
        if not normalized_code:
            raise ValueError("基金代码不能为空")
        if any(f["code"] == normalized_code for f in data["funds"]):
            raise ValueError("基金代码已存在")
        if float(current_nav) <= 0:
            raise ValueError("基金净值必须大于0")
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
            raise ValueError("基金净值必须大于0")
        for fund in data["funds"]:
            if fund["id"] == fund_id:
                fund["current_nav"] = float(nav)
                break
        else:
            raise ValueError("基金不存在")
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
            amount=round(float(price) * float(shares), 4),
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
            raise ValueError("卖出份额超过当前持仓")
        tx = Transaction(
            id=self._next_id(data, "tx"),
            fund_id=fund_id,
            tx_type="sell",
            apply_date=apply_date,
            confirm_date=confirm_date,
            price=float(price),
            shares=sell_shares,
            amount=round(float(price) * sell_shares, 4),
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
            raise ValueError("date_field must be confirm_date or apply_date")
        return sorted(txs, key=lambda x: (x[date_field], x["id"]))

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
            raise ValueError("基金不存在")

    def _total_remaining_shares(self, data: dict[str, Any], fund_id: int) -> float:
        bought = sum(tx["shares"] for tx in data["transactions"] if tx["fund_id"] == fund_id and tx["tx_type"] == "buy")
        sold = sum(tx["shares"] for tx in data["transactions"] if tx["fund_id"] == fund_id and tx["tx_type"] == "sell")
        return float(bought - sold)

    def auto_fetch_fund_info(self, code: str, target_date: str) -> tuple[str, float]:
        return self.api_client.fetch_name_and_nav(code, target_date)

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
            "holding_shares": round(holding_shares, 4),
            "holding_cost": round(holding_cost, 4),
            "avg_cost": round(avg_cost, 4),
            "market_value": round(market_value, 4),
            "floating_pnl": round(floating_pnl, 4),
            "current_nav": round(float(fund["current_nav"]), 4),
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

    @staticmethod
    def _validate_trade_inputs(apply_date: str, confirm_date: str, price: float, shares: float) -> None:
        if apply_date > confirm_date:
            raise ValueError("申请日不能晚于确认日")
        if float(price) <= 0:
            raise ValueError("价格必须大于0")
        if float(shares) <= 0:
            raise ValueError("份额必须大于0")

