from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import requests


class FundApiClient:
    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout

    def fetch_name_and_nav(self, code: str, target_date: str) -> tuple[str, float]:
        code = code.strip()
        if not code:
            raise ValueError("基金代码不能为空")
        js_text = self._fetch_fund_js(code)
        name = self._extract_name(js_text)
        nav = self._extract_nav_for_date(js_text, target_date)
        return name, nav

    def _fetch_fund_js(self, code: str) -> str:
        url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _extract_name(js_text: str) -> str:
        m = re.search(r'fS_name\s*=\s*"([^"]+)"', js_text)
        if not m:
            raise ValueError("未查询到基金名称，请确认基金代码")
        return m.group(1)

    @staticmethod
    def _extract_nav_for_date(js_text: str, target_date: str) -> float:
        m = re.search(r"Data_netWorthTrend\s*=\s*(\[[\s\S]*?\]);", js_text)
        if not m:
            raise ValueError("未查询到净值走势数据")
        trend: list[dict[str, Any]] = json.loads(m.group(1))
        if not trend:
            raise ValueError("净值走势数据为空")

        target = datetime.strptime(target_date, "%Y-%m-%d").date()
        candidate = None
        for item in trend:
            nav_date = datetime.fromtimestamp(item["x"] / 1000).date()
            if nav_date <= target:
                if candidate is None or nav_date > candidate[0]:
                    candidate = (nav_date, float(item["y"]))
        if candidate is None:
            raise ValueError("所选日期之前没有可用净值数据")
        return candidate[1]

