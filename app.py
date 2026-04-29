from __future__ import annotations

from datetime import date
import json
import os
import time

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from fundshare import __version__
from fundshare.errors import DomainError
from fundshare.service import PortfolioService


st.set_page_config(page_title="个人基金交易记录器", layout="wide", initial_sidebar_state="expanded")
with st.sidebar:
    st.markdown("### FundShare")
    st.caption(f"v{__version__}")
    st.checkbox("深色 Plotly 图表", key="fundshare_plotly_dark")
    st.divider()
    st.markdown("**快捷说明**")
    st.markdown(
        "- **基金**：新增代码、无仓删基、清空记录\n"
        "- **交易**：买卖、导入、单基净值图\n"
        "- **组合**：总览指标、持仓表与导出"
    )
    _dd = os.environ.get("DATA_DIR", "").strip()
    st.caption("数据目录：" + (_dd if _dd else "默认 `data/`，可用环境变量 `DATA_DIR`"))
    st.divider()
st.title("个人基金交易记录器")
st.caption("买入以确认日为准；卖出默认按批次指定抵扣，亦可选 FIFO；净值曲线展示买入点。")

service = PortfolioService()


def _is_locked(action: str, lock_seconds: float = 1.5) -> bool:
    ts = st.session_state.get(f"{action}_locked_at", 0.0)
    return (time.time() - ts) < lock_seconds


def _lock(action: str) -> None:
    st.session_state[f"{action}_locked_at"] = time.time()


def _format_fund_label(fund: dict) -> str:
    return f"{fund['code']} - {fund['name']} (NAV: {fund['current_nav']})"


def _auto_fill_new_fund() -> None:
    code = st.session_state.get("new_fund_code", "").strip()
    nav_date = st.session_state.get("new_fund_date", date.today())
    if not code:
        return
    try:
        auto_name, auto_nav = service.auto_fetch_fund_info(code, nav_date.isoformat())
    except Exception as e:  # noqa: BLE001
        st.session_state["new_fund_fetch_error"] = f"自动获取失败：{e}"
        return
    st.session_state["new_fund_name"] = auto_name
    st.session_state["new_fund_nav"] = float(auto_nav)
    st.session_state["new_fund_fetch_error"] = ""


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_nav_by_date(code: str, date_str: str) -> float | None:
    try:
        _, nav = service.auto_fetch_fund_info(code, date_str)
    except Exception:  # noqa: BLE001
        return None
    return float(nav)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_nav_trend_cached(code: str) -> list[dict]:
    return service.api_client.fetch_nav_trend(code)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_index_trend_cached(secid: str) -> list[dict]:
    return service.api_client.fetch_index_trend(secid)


def _fund_cumulative_pnl(summary: dict, txs: list[dict]) -> float:
    buy_amount = sum(float(tx["amount"]) for tx in txs if tx["tx_type"] == "buy")
    sell_amount = sum(float(tx["amount"]) for tx in txs if tx["tx_type"] == "sell")
    fees = sum(float(tx.get("fee", 0.0)) for tx in txs)
    market_value = float(summary["market_value"])
    return market_value + sell_amount - buy_amount - fees


def _build_holding_pnl_series(nav_points: list[dict], summary: dict) -> pd.DataFrame:
    if not nav_points:
        return pd.DataFrame()
    s = pd.DataFrame(nav_points).sort_values("date")
    holding_shares = float(summary["holding_shares"])
    holding_cost = float(summary["holding_cost"])
    s["holding_pnl"] = s["nav"].astype(float) * holding_shares - holding_cost
    return s


def _filter_nav_by_range(df: pd.DataFrame, preset: str) -> pd.DataFrame:
    if df.empty or preset == "全部":
        return df
    end_ts = pd.to_datetime(df["date"]).max()
    months_map = {"近3月": 3, "近6月": 6, "近1年": 12, "近3年": 36, "近5年": 60}
    m = months_map.get(preset)
    if m is None:
        return df
    start_ts = end_ts - pd.DateOffset(months=m)
    d = df.copy()
    d["date_ts"] = pd.to_datetime(d["date"])
    out = d[d["date_ts"] >= start_ts].drop(columns=["date_ts"])
    return out if not out.empty else df.tail(min(len(df), 90))


def _normalize_series_to_pct(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    base = float(out[value_col].iloc[0])
    if base <= 1e-12:
        return pd.DataFrame()
    out["perf_pct"] = (out[value_col].astype(float) / base - 1.0) * 100.0
    return out


def _sample_label_text(series: pd.Series, max_labels: int = 8) -> list[str | None]:
    vals = list(series)
    n = len(vals)
    if n <= max_labels:
        return [str(v) for v in vals]
    step = max(1, n // max_labels)
    out: list[str | None] = []
    for i, v in enumerate(vals):
        out.append(str(v) if i % step == 0 else None)
    return out


def _buy_lot_status_from_transactions(txs: list[dict]) -> list[dict]:
    buy_rows = [
        {
            "buy_tx_id": int(tx["id"]),
            "date": tx["confirm_date"],
            "price": float(tx["price"]),
            "original_shares": float(tx["shares"]),
            "sold_shares": 0.0,
        }
        for tx in txs
        if tx["tx_type"] == "buy"
    ]
    buy_map = {int(r["buy_tx_id"]): r for r in buy_rows}
    for tx in txs:
        if tx["tx_type"] != "sell":
            continue
        allocs = tx.get("allocations") or []
        if allocs:
            for a in allocs:
                try:
                    bid = int(a["buy_tx_id"])
                    sh = float(a["shares"])
                except (KeyError, TypeError, ValueError):
                    continue
                if bid in buy_map:
                    buy_map[bid]["sold_shares"] += sh
        else:
            # legacy sell without allocations: fallback FIFO simulation
            remaining = float(tx["shares"])
            for r in buy_rows:
                can = float(r["original_shares"]) - float(r["sold_shares"])
                if can <= 1e-9:
                    continue
                if remaining <= 1e-9:
                    break
                used = min(can, remaining)
                r["sold_shares"] += used
                remaining -= used
    for r in buy_rows:
        r["remaining_shares"] = max(0.0, float(r["original_shares"]) - float(r["sold_shares"]))
    buy_rows.sort(key=lambda x: (x["date"], x["buy_tx_id"]))
    return buy_rows


def render_fund_management() -> None:
    st.subheader("当前持有基金总览")
    funds = service.list_funds()
    if not funds:
        st.info("暂无基金数据。")
        return

    search_q = st.text_input("搜索当前持有基金（代码或名称）", "", key="fund_holdings_search").strip().lower()
    rows: list[dict] = []
    for f in funds:
        summary = service.get_position_summary(f["id"], date_field="confirm_date")
        if float(summary["holding_shares"]) <= 1e-9:
            continue
        txs = service.get_transactions(f["id"])
        cumulative_pnl = _fund_cumulative_pnl(summary, txs)
        holding_cost = float(summary["holding_cost"])
        holding_pnl = float(summary["floating_pnl"])
        rows.append(
            {
                "fund": f,
                "summary": summary,
                "txs": txs,
                "持有收益": holding_pnl,
                "持有收益率": (holding_pnl / holding_cost) if holding_cost > 1e-9 else 0.0,
                "累计盈亏": cumulative_pnl,
            }
        )

    if search_q:
        rows = [
            r
            for r in rows
            if search_q in str(r["fund"]["code"]).lower() or search_q in str(r["fund"]["name"]).lower()
        ]
    if not rows:
        st.info("当前无持仓基金，或未匹配到搜索条件。")
        return

    overview_df = pd.DataFrame(
        [
            {
                "基金代码": r["fund"]["code"],
                "基金名称": r["fund"]["name"],
                "持有份额": r["summary"]["holding_shares"],
                "持有收益": r["持有收益"],
                "持有收益率": r["持有收益率"] * 100.0,
                "累计盈亏": r["累计盈亏"],
            }
            for r in rows
        ]
    ).sort_values("持有收益", ascending=False)
    st.dataframe(
        overview_df,
        use_container_width=True,
        hide_index=True,
        column_config={"持有收益率": st.column_config.NumberColumn(format="%.2f%%")},
    )

    st.markdown("##### 持仓基金明细（可折叠）")
    plotly_tpl = "plotly_dark" if st.session_state.get("fundshare_plotly_dark") else "plotly_white"
    for r in rows:
        f = r["fund"]
        s = r["summary"]
        txs = r["txs"]
        hold_pnl = r["持有收益"]
        hold_ratio = r["持有收益率"] * 100.0
        cum_pnl = r["累计盈亏"]
        exp_title = (
            f"{f['code']} - {f['name']}  |  持有收益 {hold_pnl:.2f}  |  收益率 {hold_ratio:.2f}%  |  累计盈亏 {cum_pnl:.2f}"
        )
        with st.expander(exp_title, expanded=False):
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("基金代码", str(f["code"]))
            k2.metric("持有份额", f"{float(s['holding_shares']):.2f}")
            k3.metric("持有收益", f"{hold_pnl:.2f}")
            k4.metric("持有收益率", f"{hold_ratio:.2f}%")
            k5.metric("累计盈亏", f"{cum_pnl:.2f}")

            buy_lots = _buy_lot_status_from_transactions(txs)
            if buy_lots:
                lot_df = pd.DataFrame(buy_lots)
                lot_df["remaining_cost"] = lot_df["remaining_shares"].astype(float) * lot_df["price"].astype(float)
                st.markdown("**买入批次分布（lot）**")
                st.dataframe(
                    lot_df.rename(
                        columns={
                            "buy_tx_id": "买入ID",
                            "date": "买入日",
                            "price": "买入价",
                            "original_shares": "原始份额",
                            "sold_shares": "已卖份额",
                            "remaining_shares": "剩余份额",
                            "remaining_cost": "剩余成本",
                        }
                    )[["买入ID", "买入日", "买入价", "原始份额", "已卖份额", "剩余份额", "剩余成本"]],
                    use_container_width=True,
                    hide_index=True,
                    height=min(260, 52 + len(lot_df) * 34),
                )

            nav_points = service.get_nav_points(f["id"])
            data_source = "本地记录"
            try:
                remote_nav_points = _fetch_nav_trend_cached(f["code"])
            except Exception:  # noqa: BLE001
                remote_nav_points = []
            if remote_nav_points:
                nav_points = remote_nav_points
                data_source = "自动抓取"
            if nav_points:
                nav_df = pd.DataFrame(nav_points).sort_values("date")
                st.caption(f"走势数据来源：{data_source}")
                period = st.radio(
                    "时间段",
                    ["近3月", "近6月", "近1年", "近3年", "近5年", "全部"],
                    horizontal=True,
                    index=2,
                    key=f"fund_perf_period_{f['id']}",
                )
                nav_df = _filter_nav_by_range(nav_df, period)
                nav_df = _normalize_series_to_pct(nav_df, "nav")
                if nav_df.empty:
                    st.warning("基准净值异常（<=0），无法计算该区间涨跌幅。")
                    continue
                c_opt1, c_opt2 = st.columns(2)
                show_trade_markers = c_opt1.checkbox(
                    "显示买卖点", value=True, key=f"fund_perf_markers_{f['id']}"
                )
                show_trade_labels = c_opt2.checkbox(
                    "显示点位标签", value=False, key=f"fund_perf_marker_labels_{f['id']}"
                )
                benchmark_pick = st.selectbox(
                    "对标基准",
                    ["无", "沪深300", "中证消费"],
                    index=0,
                    key=f"fund_perf_bm_{f['id']}",
                )
                fig_nav = go.Figure()
                fig_nav.add_trace(
                    go.Scatter(
                        x=nav_df["date"],
                        y=nav_df["perf_pct"],
                        mode="lines",
                        name="本基金",
                        line={"width": 2},
                    )
                )
                bm_map = {"沪深300": "1.000300", "中证消费": "1.000932"}
                if benchmark_pick in bm_map:
                    try:
                        bm_df = pd.DataFrame(_fetch_index_trend_cached(bm_map[benchmark_pick]))
                        bm_df = _filter_nav_by_range(bm_df.rename(columns={"close": "nav"}), period)
                        bm_df = _normalize_series_to_pct(bm_df, "nav")
                        if not bm_df.empty:
                            fig_nav.add_trace(
                                go.Scatter(
                                    x=bm_df["date"],
                                    y=bm_df["perf_pct"],
                                    mode="lines",
                                    name=benchmark_pick,
                                    line={"width": 1.5, "dash": "dot"},
                                )
                            )
                    except Exception:  # noqa: BLE001
                        st.caption(f"{benchmark_pick} 对标获取失败，已忽略。")
                buy_lots = _buy_lot_status_from_transactions(txs)
                if show_trade_markers and buy_lots:
                    buy_df = pd.DataFrame(buy_lots)
                    buy_text = (
                        _sample_label_text(buy_df["original_shares"].apply(lambda v: f"买入 {float(v):.2f}份"))
                        if show_trade_labels
                        else None
                    )
                    fig_nav.add_trace(
                        go.Scatter(
                            x=buy_df["date"],
                            y=(buy_df["price"].astype(float) / float(nav_df["nav"].iloc[0]) - 1.0) * 100.0,
                            mode="markers",
                            name="买入点",
                            marker={"size": 8, "color": "#e74c3c", "symbol": "circle"},
                            text=buy_text,
                            textposition="top center",
                            customdata=buy_df[["original_shares", "sold_shares", "remaining_shares"]],
                            hovertemplate=(
                                "买入日=%{x}<br>点位=%{y:.2f}%"
                                "<br>原始份额=%{customdata[0]:.2f}"
                                "<br>已卖份额=%{customdata[1]:.2f}"
                                "<br>剩余份额=%{customdata[2]:.2f}<extra></extra>"
                            ),
                        )
                    )
                fig_nav.update_layout(
                    title="业绩走势",
                    xaxis_title="日期",
                    yaxis_title="涨跌幅(%)",
                    template=plotly_tpl,
                    xaxis_rangeslider_visible=True,
                )
                st.plotly_chart(fig_nav, use_container_width=True)

                pnl_df = _build_holding_pnl_series(nav_points, s)
                if not pnl_df.empty:
                    fig_pnl = go.Figure()
                    fig_pnl.add_trace(
                        go.Scatter(
                            x=pnl_df["date"],
                            y=pnl_df["holding_pnl"],
                            mode="lines",
                            name="持仓口径累计盈亏",
                            line={"width": 2},
                        )
                    )
                    fig_pnl.update_layout(
                        title="累计盈亏走势（按当前持仓口径）",
                        xaxis_title="日期",
                        yaxis_title="累计盈亏",
                        template=plotly_tpl,
                        xaxis_rangeslider_visible=True,
                    )
                    st.plotly_chart(fig_pnl, use_container_width=True)
            else:
                st.caption("暂无净值点，无法展示走势。")

            if txs:
                tx_df = pd.DataFrame(txs).sort_values("confirm_date", ascending=False)
                if "fee" not in tx_df.columns:
                    tx_df["fee"] = 0.0
                st.markdown("**最近交易摘要（最近8笔）**")
                st.dataframe(
                    tx_df.rename(
                        columns={
                            "tx_type": "类型",
                            "apply_date": "申请日",
                            "confirm_date": "确认日",
                            "price": "价格",
                            "shares": "份额",
                            "amount": "金额",
                            "fee": "手续费",
                        }
                    )[["类型", "申请日", "确认日", "价格", "份额", "金额", "手续费"]].head(8),
                    use_container_width=True,
                    hide_index=True,
                    height=min(300, 52 + min(len(tx_df), 8) * 36),
                )


def render_maintenance() -> None:
    st.subheader("基金维护")
    st.caption("仅用于：添加基金、删除基金、删除单条交易、一键清空单基金全部记录。")

    if "new_fund_code" not in st.session_state:
        st.session_state["new_fund_code"] = ""

    c1, c2 = st.columns([2.0, 1.0])
    st.session_state["new_fund_code"] = c1.text_input(
        "基金代码",
        value=st.session_state["new_fund_code"],
        placeholder="如 161725",
        key="maint_new_fund_code",
    )
    add_clicked = c2.button("按代码自动新增基金", use_container_width=True, disabled=_is_locked("add_fund"))
    if add_clicked:
        code = st.session_state["new_fund_code"]
        if not code.strip():
            st.error("基金代码不能为空。")
        else:
            try:
                name, nav = service.auto_fetch_fund_info(code, date.today().isoformat())
            except Exception as e:  # noqa: BLE001
                st.error(f"新增失败：{e}")
            else:
                service.add_fund(code, name, nav, date.today().isoformat())
                st.success(f"基金已新增：{name}，当前净值 {nav:.4f}")
                st.session_state["new_fund_code"] = ""
                _lock("add_fund")
                st.rerun()

    funds = service.list_funds()
    if not funds:
        st.info("暂无基金数据。")
        return
    ui_seq = {int(f["id"]): i + 1 for i, f in enumerate(funds)}
    maint_labels = {
        f"[#{ui_seq[int(f['id'])]}] {_format_fund_label(f)}": int(f["id"])
        for f in funds
    }

    maint_df = pd.DataFrame(
        [
            {
                "序号": ui_seq[int(f["id"])],
                "代码": f["code"],
                "名称": f["name"],
                "当前净值": f["current_nav"],
            }
            for f in funds
        ]
    )
    st.dataframe(
        maint_df,
        use_container_width=True,
        hide_index=True,
        height=min(320, 52 + len(funds) * 36),
    )

    with st.expander("删除基金（无持仓时）"):
        del_pick = st.selectbox("选择要删除的基金", options=list(maint_labels.keys()), key="maint_fund_delete_pick")
        if st.button("确认删除该基金及其历史净值与交易", key="maint_fund_delete_btn"):
            try:
                service.delete_fund(maint_labels[del_pick])
            except DomainError as e:
                st.error(str(e))
            else:
                st.success("已删除。")
                st.rerun()

    with st.expander("一键清空某基金的所有记录（交易+净值）", expanded=False):
        clr_pick = st.selectbox("选择要清空记录的基金", options=list(maint_labels.keys()), key="maint_fund_clear_pick")
        clr_confirm = st.checkbox("我确认清空该基金全部交易与净值记录", value=False, key="maint_fund_clear_confirm")
        if st.button("确认清空该基金记录", key="maint_fund_clear_btn", type="primary"):
            if not clr_confirm:
                st.error("请先勾选确认。")
            else:
                service.clear_fund_records(maint_labels[clr_pick])
                st.success("该基金历史记录已清空。")
                st.rerun()

    with st.expander("危险操作：一键删除基金及全部记录", expanded=False):
        st.warning("该操作会删除基金本体、全部交易和全部净值点，不可恢复。")
        purge_pick = st.selectbox("选择要一键删除的基金", options=list(maint_labels.keys()), key="maint_fund_purge_pick")
        purge_phrase = st.text_input("请输入 DELETE 以确认", value="", key="maint_fund_purge_phrase")
        if st.button("一键删除基金及全部记录", key="maint_fund_purge_btn", type="primary"):
            if purge_phrase.strip().upper() != "DELETE":
                st.error("确认词不正确，请输入 DELETE。")
            else:
                try:
                    service.purge_fund(maint_labels[purge_pick])
                except DomainError as e:
                    st.error(str(e))
                else:
                    st.success("基金及其所有记录已删除。")
                    st.rerun()

    with st.expander("删除买入/卖出记录", expanded=False):
        tx_fund_pick = st.selectbox("选择基金", options=list(maint_labels.keys()), key="maint_tx_fund_pick")
        tx_fund_id = maint_labels[tx_fund_pick]
        tx_rows = service.get_transactions(tx_fund_id, date_field="confirm_date")
        if not tx_rows:
            st.caption("该基金暂无交易记录。")
        else:
            tx_preview = pd.DataFrame(tx_rows).sort_values(["confirm_date", "id"], ascending=[False, False]).rename(
                columns={
                    "id": "ID",
                    "tx_type": "类型",
                    "apply_date": "申请日",
                    "confirm_date": "确认日",
                    "price": "价格",
                    "shares": "份额",
                    "amount": "金额",
                    "fee": "手续费",
                }
            )
            st.dataframe(
                tx_preview[["ID", "类型", "申请日", "确认日", "价格", "份额", "金额", "手续费"]],
                use_container_width=True,
                hide_index=True,
                height=min(260, 52 + len(tx_preview) * 34),
            )
            tx_label_map = {
                f"#{tx['id']} {tx['tx_type']} {tx['confirm_date']} 份额:{float(tx['shares']):.2f} 价格:{float(tx['price']):.4f}": int(tx["id"])
                for tx in tx_rows
            }
            tx_pick_label = st.selectbox("选择要删除的交易", options=list(tx_label_map.keys()), key="maint_tx_delete_pick")
            confirmed = st.checkbox("我确认删除该交易记录", value=False, key="maint_tx_delete_confirm")
            if st.button("确认删除交易", key="maint_tx_delete_btn", type="primary"):
                if not confirmed:
                    st.error("请先勾选确认。")
                else:
                    try:
                        service.delete_transaction(tx_fund_id, tx_label_map[tx_pick_label])
                    except DomainError as e:
                        st.error(str(e))
                    else:
                        st.success("交易记录已删除。")
                        st.rerun()


def render_trades_and_chart() -> None:
    st.subheader("交易与净值")
    funds = service.list_funds()
    if not funds:
        st.info("请先在「基金管理」中新增基金。")
        return

    with st.container(border=True):
        st.markdown("**分析口径**")
        st.caption("仅按确认日（与支付宝买入基金确认日一致）")
        date_field = "confirm_date"
        analysis_basis = "按确认日"
        options = {_format_fund_label(f): f["id"] for f in funds}
        selected_label = st.selectbox(
            "当前基金",
            list(options.keys()),
            help="切换基金后，下方交易、筛选与图表均针对该基金。",
        )
        fund_id = options[selected_label]
        selected_fund = next(f for f in funds if f["id"] == fund_id)

    remaining_shares = service.get_remaining_shares(fund_id)
    summary = service.get_position_summary(fund_id, date_field=date_field)
    st.markdown("##### 持仓快照")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("持仓份额", f"{summary['holding_shares']:.2f}")
    m2.metric("持仓成本", f"{summary['holding_cost']:.2f}")
    m3.metric("当前净值", f"{summary['current_nav']:.4f}")
    m4.metric("估值", f"{summary['market_value']:.2f}")
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("浮动盈亏", f"{summary['floating_pnl']:.2f}")
    m6.metric("加权持仓天数", f"{summary['avg_holding_days']:.1f}", help="按剩余份额加权")
    m7.metric("最早买入天数", f"{summary['first_lot_age_days']:.1f}")
    m8.metric("简易年化", f"{summary['annualized_simple_ratio'] * 100:.2f}%", help="浮盈/成本，按加权持仓天数线性折算年率")

    t1, t2 = st.columns(2)
    with t1:
        with st.container(border=True):
            st.markdown("**买入**")
            confirm_d = st.date_input("买入确认日", value=date.today(), key=f"buy_confirm_date_{fund_id}")
            buy_mode = st.radio(
                "买入录入方式",
                ["按净值+份额", "按金额+份额（自动算净值）"],
                horizontal=True,
                key=f"buy_mode_{fund_id}",
            )
            auto_price = st.checkbox("确认日自动净值", value=True, key=f"buy_auto_price_{fund_id}")
            buy_auto_nav = _fetch_nav_by_date(selected_fund["code"], confirm_d.isoformat())

            if buy_mode == "按净值+份额":
                if auto_price and buy_auto_nav is not None:
                    price = float(buy_auto_nav)
                    st.info(f"买入确认净值（自动）: {price:.4f}")
                else:
                    if auto_price and buy_auto_nav is None:
                        st.warning("未获取到确认日净值，请取消勾选后手动输入。")
                    price = st.number_input(
                        "买入确认净值",
                        min_value=0.0001,
                        value=1.0,
                        step=0.0001,
                        format="%.4f",
                        key=f"buy_price_{fund_id}",
                    )
                buy_preset = st.selectbox("买入份额快捷", ["自定义", "100", "500", "1000", "5000"], key=f"buy_preset_{fund_id}")
                is_custom = buy_preset == "自定义"
                preset_val = 100.0 if is_custom else float(buy_preset)
                shares_input = st.number_input(
                    "买入份额",
                    min_value=0.0001,
                    value=preset_val,
                    step=1.0,
                    format="%.2f",
                    disabled=not is_custom,
                    key=f"buy_shares_{fund_id}",
                )
                shares = float(shares_input if is_custom else preset_val)
                amount = round(float(price) * float(shares), 2)
            else:
                shares = st.number_input(
                    "买入份额",
                    min_value=0.0001,
                    value=100.0,
                    step=1.0,
                    format="%.2f",
                    key=f"buy_shares_amt_mode_{fund_id}",
                )
                amount = st.number_input(
                    "买入金额",
                    min_value=0.0001,
                    value=100.0,
                    step=0.01,
                    format="%.2f",
                    key=f"buy_amount_{fund_id}",
                )
                price = round(float(amount) / float(shares), 6)
                st.info(f"自动计算净值: {price:.6f}")

            buy_fee = st.number_input(
                "手续费（可选）", min_value=0.0, value=0.0, step=0.01, format="%.2f", key=f"buy_fee_{fund_id}"
            )
            st.write(f"本次买入金额: **{amount:.2f}**")
            if st.button("记录买入", key=f"buy_submit_{fund_id}", disabled=_is_locked("buy_tx")):
                try:
                    cd = confirm_d.isoformat()
                    service.add_buy(fund_id, cd, cd, float(price), float(shares), float(buy_fee))
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.success("买入记录已保存。")
                    _lock("buy_tx")
                    st.rerun()

    with t2:
        with st.container(border=True):
            st.markdown("**卖出**")
            st.caption(f"当前可卖出份额：{remaining_shares:.2f}")
            sell_mode = st.radio(
                "卖出方式",
                ["FIFO 自动", "指定买入批次"],
                horizontal=True,
                index=1,
                key=f"sell_mode_{fund_id}",
            )
            picks: list[dict] = []
            lot_total = 0.0
            if sell_mode == "指定买入批次":
                lots = service.get_sellable_buy_lots(fund_id, date_field="confirm_date")
                lot_map = {
                    f"买入#{int(l['buy_id'])} {l['date']} 价:{float(l['price']):.4f} 剩:{float(l['remaining_shares']):.2f}": l
                    for l in lots
                    if float(l["remaining_shares"]) > 1e-9
                }
                chosen = st.multiselect("选择要抵扣的买入批次", options=list(lot_map.keys()), key=f"sell_lot_pick_{fund_id}")
                for label in chosen:
                    lot = lot_map[label]
                    max_sh = float(lot["remaining_shares"])
                    sh = st.number_input(
                        f"批次#{int(lot['buy_id'])} 卖出份额",
                        min_value=0.0,
                        max_value=max_sh,
                        value=max_sh,
                        step=1.0,
                        format="%.2f",
                        key=f"sell_lot_sh_{fund_id}_{int(lot['buy_id'])}",
                    )
                    if sh > 0:
                        picks.append({"buy_tx_id": int(lot["buy_id"]), "shares": float(sh)})
                        lot_total += float(sh)
                st.caption(f"本次卖出总份额：{lot_total:.2f}")

            confirm_d = st.date_input("卖出确认日", value=date.today(), key=f"sell_confirm_date_{fund_id}")
            sell_entry_mode = st.radio(
                "卖出录入方式",
                ["按净值+份额", "按金额+份额（自动算净值）"],
                horizontal=True,
                key=f"sell_entry_mode_{fund_id}",
            )
            if sell_mode == "FIFO 自动":
                sell_preset = st.selectbox(
                    "卖出比例快捷",
                    ["自定义", "25%", "50%", "75%", "100%"],
                    key=f"sell_preset_{fund_id}",
                )
                if sell_preset == "自定义":
                    default_sell = min(100.0, remaining_shares) if remaining_shares > 0 else 0.0001
                else:
                    pct = float(sell_preset.rstrip("%")) / 100.0
                    default_sell = max(
                        0.0001,
                        min(float(remaining_shares), float(remaining_shares) * pct) if remaining_shares > 0 else 0.0001,
                    )
                shares = st.number_input(
                    "卖出份额",
                    min_value=0.0001,
                    max_value=max(0.0001, remaining_shares),
                    value=default_sell,
                    step=1.0,
                    format="%.2f",
                    key=f"sell_shares_{fund_id}_{sell_preset}_{sell_entry_mode}",
                )
            else:
                shares = lot_total

            sell_auto_nav = _fetch_nav_by_date(selected_fund["code"], confirm_d.isoformat())
            if sell_entry_mode == "按净值+份额":
                auto_price = st.checkbox("确认日自动净值", value=True, key=f"sell_auto_price_{fund_id}")
                if auto_price and sell_auto_nav is not None:
                    price = float(sell_auto_nav)
                    st.info(f"卖出确认净值（自动）: {price:.4f}")
                else:
                    if auto_price and sell_auto_nav is None:
                        st.warning("未获取到确认日净值，请取消勾选后手动输入。")
                    price = st.number_input(
                        "卖出确认净值",
                        min_value=0.0001,
                        value=1.0,
                        step=0.0001,
                        format="%.4f",
                        key=f"sell_price_{fund_id}",
                    )
                amount = round(float(price) * float(shares), 2)
            else:
                if sell_mode == "指定买入批次" and shares <= 1e-9:
                    st.warning("请先选择并填写要抵扣的买入批次份额。")
                amount = st.number_input(
                    "卖出金额",
                    min_value=0.0001,
                    value=100.0,
                    step=0.01,
                    format="%.2f",
                    key=f"sell_amount_{fund_id}",
                )
                price = round(float(amount) / float(shares), 6) if float(shares) > 1e-9 else 0.0
                st.info(f"自动计算净值: {price:.6f}")

            sell_fee = st.number_input(
                "手续费（可选）", min_value=0.0, value=0.0, step=0.01, format="%.2f", key=f"sell_fee_{fund_id}"
            )
            st.write(f"本次卖出金额: **{amount:.2f}**")
            sell_risk = service.classify_sell_risk(remaining_shares, float(shares))
            sell_confirmed = True
            if sell_risk in ("large", "clearout"):
                tip = "清仓卖出" if sell_risk == "clearout" else "大额卖出（≥50%持仓）"
                st.warning(f"{tip}：请勾选下方确认后再提交。")
                sell_confirmed = st.checkbox(
                    "我已核对份额与价格，确认提交本次卖出", value=False, key=f"sell_confirm_{fund_id}"
                )
            if st.button("记录卖出", key=f"sell_submit_{fund_id}", disabled=_is_locked("sell_tx")):
                if sell_risk in ("large", "clearout") and not sell_confirmed:
                    st.error("请先勾选确认后再提交卖出。")
                else:
                    try:
                        cd = confirm_d.isoformat()
                        if sell_mode == "FIFO 自动":
                            service.add_sell(fund_id, cd, cd, float(price), float(shares), float(sell_fee))
                        else:
                            service.add_sell_by_lots(fund_id, cd, cd, float(price), picks, float(sell_fee))
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.success("卖出记录已保存。")
                        _lock("sell_tx")
                        st.rerun()

    st.markdown("##### 筛选与交易表")
    filter_c1, filter_c2, filter_c3 = st.columns([1, 1, 1])
    tx_start = filter_c1.date_input("开始日期", value=date.today().replace(day=1), key="tx_filter_start")
    tx_end = filter_c2.date_input("结束日期", value=date.today(), key="tx_filter_end")
    tx_type_label = filter_c3.selectbox("类型", ["全部", "仅买入", "仅卖出"], index=0)
    tx_type_map = {"全部": "all", "仅买入": "buy", "仅卖出": "sell"}
    if tx_start > tx_end:
        st.warning("开始日期不能晚于结束日期，将显示全部交易。")
        transactions = service.get_transactions(fund_id, date_field=date_field)
    else:
        transactions = service.filter_transactions_by_date_range(
            fund_id,
            tx_start.isoformat(),
            tx_end.isoformat(),
            date_field=date_field,
        )
    transactions = service.filter_transactions_by_type(transactions, tx_type=tx_type_map[tx_type_label])

    if transactions:
        tx_df = pd.DataFrame(transactions)
        if "fee" not in tx_df.columns:
            tx_df["fee"] = 0.0
        tx_df = tx_df.rename(
            columns={
                "tx_type": "交易类型",
                "apply_date": "申请日",
                "confirm_date": "确认日",
                "price": "价格",
                "shares": "份额",
                "amount": "金额",
                "fee": "手续费",
            }
        )
        st.dataframe(
            tx_df[["交易类型", "确认日", "价格", "份额", "金额", "手续费"]],
            use_container_width=True,
            hide_index=True,
            height=min(400, 52 + len(transactions) * 36),
            column_config={
                "金额": st.column_config.NumberColumn(format="%.2f"),
                "手续费": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    else:
        st.caption("当前筛选条件下暂无交易记录。")

    with st.expander("批量导入（JSON / CSV）", expanded=False):
        st.caption("导入针对上方**当前基金**；成功后会自动刷新页面。")
        tjson, tcsv = st.tabs(["JSON", "CSV"])
        with tjson:
            st.caption(
                "根字段 `fund_code` + `transactions`；每条含 `tx_type`、`apply_date`、`confirm_date`、"
                "`price`、`shares`；可选 `fee`。"
            )
            j1, j2 = st.columns(2)
            with j1:
                tx_import_text = st.text_area("粘贴 JSON", height=140, key=f"tx_import_text_{fund_id}")
            if st.button("执行 JSON 导入", type="primary", key=f"tx_import_run_{fund_id}"):
                if not tx_import_text.strip():
                    st.warning("请先粘贴 JSON。")
                else:
                    try:
                        n_imported = service.import_transactions_json(tx_import_text)
                        st.success(f"已导入 {n_imported} 条交易。")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
        with tcsv:
            st.caption(
                "表头须含 `tx_type` `apply_date` `confirm_date` `price` `shares`；可选 `amount`、`fee`。"
            )
            c1, c2 = st.columns(2)
            with c1:
                tx_import_csv_text = st.text_area("粘贴 CSV", height=140, key=f"tx_import_csv_{fund_id}")
                uploaded_csv = st.file_uploader("或上传 .csv", type=["csv"], key=f"tx_upload_csv_{fund_id}")
            csv_payload = tx_import_csv_text.strip()
            if uploaded_csv is not None:
                try:
                    csv_payload = uploaded_csv.getvalue().decode("utf-8-sig")
                except UnicodeDecodeError:
                    st.error("CSV 解码失败，请使用 UTF-8。")
            if st.button("执行 CSV 导入", type="primary", key=f"tx_csv_run_{fund_id}"):
                if not csv_payload.strip():
                    st.warning("请先粘贴或上传 CSV。")
                else:
                    try:
                        n_csv = service.import_transactions_csv(csv_payload, selected_fund["code"])
                        st.success(f"已导入 {n_csv} 条交易。")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    nav_points = service.get_nav_points(fund_id)
    try:
        remote_nav_points = _fetch_nav_trend_cached(selected_fund["code"])
    except Exception:  # noqa: BLE001
        remote_nav_points = []
    if remote_nav_points:
        nav_points = remote_nav_points
    if not nav_points:
        st.info("暂无净值数据，无法绘制曲线。")
        return
    st.markdown("##### 净值曲线")
    chart_key = f"nav_chart_range_{fund_id}"
    if chart_key not in st.session_state:
        st.session_state[chart_key] = "近1年"
    chart_range = str(st.session_state[chart_key])
    span_days_map = {"近3月": 90, "近6月": 180, "近1年": 365, "近3年": 1095, "近5年": 1825}
    total_days = 0
    if nav_points:
        nav_dates = sorted(pd.to_datetime(pd.DataFrame(nav_points)["date"]))
        if len(nav_dates) >= 2:
            total_days = int((nav_dates[-1] - nav_dates[0]).days)
    need_days = span_days_map.get(chart_range, 0)
    if need_days > 0 and total_days > 0 and total_days < need_days:
        years = "3年" if chart_range == "近3年" else "5年" if chart_range == "近5年" else chart_range
        st.warning(f"该基金成立时长不足{years}，当前将展示可用的全部历史区间。")

    win_start, win_end = service.nav_chart_date_window(nav_points, chart_range)
    nav_filtered = service.filter_records_by_date_range(nav_points, "date", win_start, win_end)
    nav_df = pd.DataFrame(nav_filtered).sort_values("date")
    if nav_df.empty:
        st.info("当前时间范围内没有净值数据，请选择「全部」或更长区间。")
        return
    tx_all = service.get_transactions(fund_id, date_field="confirm_date")
    buy_lots_all = _buy_lot_status_from_transactions(tx_all)
    buy_points_raw = [
        {
            "date": r["date"],
            "price": float(r["price"]),
            "original_shares": float(r["original_shares"]),
            "remaining_shares": float(r["remaining_shares"]),
        }
        for r in buy_lots_all
    ]
    if buy_points_raw:
        buy_df_all = pd.DataFrame(buy_points_raw)
        agg_df = (
            buy_df_all.groupby("date", as_index=False)
            .agg(
                buy_count=("date", "size"),
                original_shares=("original_shares", "sum"),
                remaining_shares=("remaining_shares", "sum"),
                weighted_cost=("price", lambda s: float((s * buy_df_all.loc[s.index, "original_shares"]).sum())),
            )
            .sort_values("date")
        )
        agg_df["price"] = agg_df["weighted_cost"] / agg_df["original_shares"].where(agg_df["original_shares"] > 1e-12, 1.0)
        buy_points = agg_df[["date", "price", "buy_count", "original_shares", "remaining_shares"]].to_dict("records")
    else:
        buy_points = []
    buy_points = service.filter_records_by_date_range(buy_points, "date", win_start, win_end)

    gaps = service.nav_point_calendar_gaps(nav_filtered, min_gap_days=14)
    with st.expander("净值曲线说明与数据间隔", expanded=False):
        st.markdown(
            "- **折线**连接的是已写入的净值点（含手动更新与自动抓取）。\n"
            "- 自动填入价格时：若所选日没有净值，会使用**不晚于该日的最近净值**（与常见披露一致）。\n"
            "- 相邻两点日历间隔过长，通常对应长假或未录入期间。"
        )
        if gaps:
            st.warning(f"当前范围内有 {len(gaps)} 处相邻记录间隔超过 14 天（可按需补录净值）。")
            for prev_d, next_d, days in gaps[:8]:
                st.caption(f"{prev_d} → {next_d}，间隔 **{days}** 天")

    plotly_tpl = "plotly_dark" if st.session_state.get("fundshare_plotly_dark") else "plotly_white"
    show_nav_dod = st.checkbox(
        "显示相邻净值点涨跌幅（右轴，%）",
        value=False,
        key=f"nav_dod_{fund_id}",
    )
    nav_pct = (nav_df["nav"].astype(float).pct_change() * 100.0).fillna(0.0)
    nav_base = float(nav_df["nav"].iloc[0]) if not nav_df.empty else 1.0
    nav_dtick = max(0.0001, round(nav_base * 0.04, 4))

    if show_nav_dod:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=nav_df["date"],
                y=nav_df["nav"],
                mode="lines",
                name="净值走势",
                line={"width": 2.5, "color": "#f5a623"},
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=nav_df["date"],
                y=nav_pct,
                mode="lines",
                name="点间涨跌%",
                line={"dash": "dot", "width": 1.2, "color": "#95a5a6"},
            ),
            secondary_y=True,
        )
        if buy_points:
            open_df = pd.DataFrame(buy_points)
            buy_symbols = open_df["remaining_shares"].apply(lambda v: "circle-open" if float(v) <= 1e-9 else "circle").tolist()
            fig.add_trace(
                go.Scatter(
                    x=open_df["date"],
                    y=open_df["price"],
                    mode="markers",
                    name="买入点",
                    marker={"color": "#f25278", "size": 8, "symbol": buy_symbols},
                    text=open_df.apply(
                        lambda row: f"当日买入笔数: {int(row['buy_count'])} | 买入份额: {float(row['original_shares']):.2f} | 剩余份额: {float(row['remaining_shares']):.2f}",
                        axis=1,
                    ),
                    hoverlabel={"font": {"size": 16}},
                    hovertemplate="日期=%{x}<br>买入净值=%{y:.4f}<br>%{text}<extra></extra>",
                ),
                secondary_y=False,
            )
        fig.update_layout(
            title="",
            legend_title="图例",
            template=plotly_tpl,
            xaxis_rangeslider_visible=True,
            legend={"orientation": "h", "y": 1.05, "x": 0.0},
        )
        fig.update_xaxes(title_text="日期")
        fig.update_yaxes(title_text="净值", secondary_y=False)
        fig.update_yaxes(title_text="环比涨跌幅 %", secondary_y=True)
        fig.update_yaxes(dtick=nav_dtick, secondary_y=False)
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=nav_df["date"],
                y=nav_df["nav"],
                mode="lines",
                name="净值走势",
                line={"width": 2.5, "color": "#f5a623"},
            )
        )
        if buy_points:
            open_df = pd.DataFrame(buy_points)
            buy_symbols = open_df["remaining_shares"].apply(lambda v: "circle-open" if float(v) <= 1e-9 else "circle").tolist()
            fig.add_trace(
                go.Scatter(
                    x=open_df["date"],
                    y=open_df["price"],
                    mode="markers",
                    name="买入点",
                    marker={"color": "#f25278", "size": 8, "symbol": buy_symbols},
                    text=open_df.apply(
                        lambda row: f"当日买入笔数: {int(row['buy_count'])} | 买入份额: {float(row['original_shares']):.2f} | 剩余份额: {float(row['remaining_shares']):.2f}",
                        axis=1,
                    ),
                    hoverlabel={"font": {"size": 16}},
                    hovertemplate="日期=%{x}<br>买入净值=%{y:.4f}<br>%{text}<extra></extra>",
                )
            )
        else:
            st.caption("当前区间内无买入点。")
        fig.update_layout(
            title="",
            xaxis_title="日期",
            yaxis_title="净值",
            legend_title="图例",
            template=plotly_tpl,
            xaxis_rangeslider_visible=True,
            legend={"orientation": "h", "y": 1.05, "x": 0.0},
        )
        fig.update_yaxes(dtick=nav_dtick)
    st.plotly_chart(fig, use_container_width=True)
    _r1, r_mid, _r3 = st.columns([1, 3, 1])
    with r_mid:
        st.radio(
            "区间",
            ["近3月", "近6月", "近1年", "近3年", "近5年", "全部"],
            horizontal=True,
            key=chart_key,
        )

tab1, tab2, tab3, tab4 = st.tabs(["组合总览", "基金管理", "交易与净值", "维护"])
with tab1:
    overview = service.get_portfolio_overview()
    st.subheader("组合概览")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("总成本", f"{overview['total_cost']:.2f}")
    o2.metric("总市值", f"{overview['total_value']:.2f}")
    o3.metric("浮动盈亏", f"{overview['total_pnl']:.2f}")
    o4.metric("组合收益率", f"{overview['pnl_ratio'] * 100:.2f}%")
    o5, o6, o7, o8 = st.columns(4)
    o5.metric("累计买入", f"{overview['buy_amount']:.2f}")
    o6.metric("累计卖出", f"{overview['sell_amount']:.2f}")
    o7.metric("已实现盈亏", f"{overview['realized_pnl']:.2f}")
    o8.metric("累计手续费", f"{overview['total_fees']:.2f}")
    st.caption(f"扣费后已实现盈亏：**{overview['realized_pnl_after_fees']:.2f}**")
    st.divider()
    st.subheader("多基金持仓对比")
    all_summaries = service.get_all_position_summaries()
    if all_summaries:
        summary_df = pd.DataFrame(all_summaries).rename(
            columns={
                "code": "基金代码",
                "name": "基金名称",
                "holding_shares": "持仓份额",
                "holding_cost": "持仓成本",
                "avg_cost": "持仓均价",
                "current_nav": "当前净值",
                "market_value": "估值",
                "floating_pnl": "浮动盈亏",
                "avg_holding_days": "加权持仓天数",
                "first_lot_age_days": "最早买入天数",
                "annualized_simple_ratio": "简易年化",
            }
        )
        summary_df["简易年化"] = summary_df["简易年化"].apply(lambda r: float(r) * 100.0)
        st.dataframe(
            summary_df[
                [
                    "基金代码",
                    "基金名称",
                    "持仓份额",
                    "持仓成本",
                    "持仓均价",
                    "当前净值",
                    "估值",
                    "浮动盈亏",
                    "加权持仓天数",
                    "最早买入天数",
                    "简易年化",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
        rank_df = summary_df.copy()
        rank_df["收益率"] = rank_df.apply(
            lambda row: (row["浮动盈亏"] / row["持仓成本"]) if row["持仓成本"] and float(row["持仓成本"]) > 0 else 0.0,
            axis=1,
        )
        rank_df = rank_df.sort_values("收益率", ascending=False)
        st.subheader("收益率排行（按持仓成本口径）")
        st.dataframe(
            rank_df[["基金代码", "基金名称", "收益率", "浮动盈亏", "持仓成本"]],
            use_container_width=True,
            hide_index=True,
        )
        bar_df = summary_df[["基金代码", "浮动盈亏"]]
        st.bar_chart(bar_df, x="基金代码", y="浮动盈亏")
    else:
        st.info("暂无基金数据。")
with tab2:
    render_fund_management()
with tab3:
    render_trades_and_chart()
with tab4:
    render_maintenance()

