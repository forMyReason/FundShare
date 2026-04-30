"""供 Kotlin 调用的最小入口：验证 JsonStorage + PortfolioService 在 Android 本地目录可用。"""

from __future__ import annotations

import os


def _ensure_data_dir() -> None:
    """Chaquopy 将 HOME 设为应用私有目录；与 JsonStorage 的 DATA_DIR 约定对齐。"""
    home = (os.environ.get("HOME") or "").strip()
    if home and not (os.environ.get("DATA_DIR") or "").strip():
        os.environ["DATA_DIR"] = home


def get_status_line() -> str:
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
