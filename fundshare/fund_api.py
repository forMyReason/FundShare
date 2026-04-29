from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

import requests


class FundApiClient:
    def __init__(self, timeout: float = 8.0, js_cache_ttl_sec: float = 120.0) -> None:
        self.timeout = timeout
        self.js_cache_ttl_sec = js_cache_ttl_sec
        self._js_cache: dict[str, tuple[float, str]] = {}

    def fetch_name_and_nav(self, code: str, target_date: str) -> tuple[str, float]:
        code = code.strip()
        if not code:
            raise ValueError("基金代码不能为空")
        js_text = self._fetch_fund_js(code)
        name = self._extract_name(js_text)
        nav = self._extract_nav_for_date(js_text, target_date)
        return name, nav

    def fetch_nav_trend(self, code: str) -> list[dict[str, Any]]:
        code = code.strip()
        if not code:
            raise ValueError("基金代码不能为空")
        js_text = self._fetch_fund_js(code)
        trend = self._extract_nav_trend(js_text)
        rows: list[dict[str, Any]] = []
        for item in trend:
            rows.append(
                {
                    "date": datetime.fromtimestamp(item["x"] / 1000).date().isoformat(),
                    "nav": float(item["y"]),
                }
            )
        rows.sort(key=lambda r: r["date"])
        return rows

    def fetch_index_trend(self, secid: str) -> list[dict[str, Any]]:
        """Fetch index daily close trend from Eastmoney kline API.

        secid examples:
        - 1.000300 (沪深300)
        - 1.000932 (中证消费)
        """
        secid = secid.strip()
        if not secid:
            raise ValueError("secid 不能为空")
        url = (
            "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            "&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            "&klt=101&fqt=1&beg=0&end=20500000"
        )
        last_exc: requests.RequestException | None = None
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return self._extract_index_klines(resp.text)
            except requests.RequestException as e:
                last_exc = e
                if attempt < 2:
                    time.sleep(0.35 * (attempt + 1))
        if last_exc is None:
            raise RuntimeError("unexpected fetch state")
        raise last_exc

    def _fetch_fund_js(self, code: str) -> str:
        now = time.monotonic()
        hit = self._js_cache.get(code)
        if hit is not None and (now - hit[0]) < self.js_cache_ttl_sec:
            return hit[1]
        url = f"http://fund.eastmoney.com/pingzhongdata/{code}.js"
        last_exc: requests.RequestException | None = None
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                text = resp.text
                self._js_cache[code] = (now, text)
                return text
            except requests.RequestException as e:
                last_exc = e
                if attempt < 2:
                    time.sleep(0.35 * (attempt + 1))
        if last_exc is None:
            raise RuntimeError("unexpected fetch state")
        raise last_exc

    @staticmethod
    def _extract_name(js_text: str) -> str:
        m = re.search(r'fS_name\s*=\s*"([^"]+)"', js_text)
        if not m:
            raise ValueError("未查询到基金名称，请确认基金代码")
        return m.group(1)

    @staticmethod
    def _extract_nav_for_date(js_text: str, target_date: str) -> float:
        trend = FundApiClient._extract_nav_trend(js_text)

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

    @staticmethod
    def _extract_nav_trend(js_text: str) -> list[dict[str, Any]]:
        m = re.search(r"Data_netWorthTrend\s*=\s*(\[[\s\S]*?\]);", js_text)
        if not m:
            raise ValueError("未查询到净值走势数据")
        trend: list[dict[str, Any]] = json.loads(m.group(1))
        if not trend:
            raise ValueError("净值走势数据为空")
        return trend

    @staticmethod
    def _extract_index_klines(text: str) -> list[dict[str, Any]]:
        try:
            payload = json.loads(text)
            klines = payload["data"]["klines"]
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            raise ValueError("指数走势解析失败") from e
        if not klines:
            raise ValueError("指数走势数据为空")
        rows: list[dict[str, Any]] = []
        for row in klines:
            parts = str(row).split(",")
            if len(parts) < 3:
                continue
            rows.append({"date": parts[0], "close": float(parts[2])})
        rows.sort(key=lambda r: r["date"])
        return rows

