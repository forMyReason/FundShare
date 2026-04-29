from __future__ import annotations

from datetime import date
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fundshare.service import PortfolioService


st.set_page_config(page_title="个人基金交易记录器", layout="wide")
st.title("个人基金交易记录器")
st.caption("记录基金买卖，按FIFO抵扣份额，并在净值曲线上标注仍持有份额的买入点。")

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


def render_fund_management() -> None:
    st.subheader("1) 基金基础信息管理")
    if "new_fund_code" not in st.session_state:
        st.session_state["new_fund_code"] = ""
    if "new_fund_name" not in st.session_state:
        st.session_state["new_fund_name"] = "-"
    if "new_fund_nav" not in st.session_state:
        st.session_state["new_fund_nav"] = 0.0

    c1, c2 = st.columns([2.0, 1.0])
    st.session_state["new_fund_code"] = c1.text_input(
        "基金代码",
        value=st.session_state["new_fund_code"],
        placeholder="如 161725",
    )
    add_clicked = c2.button("按代码自动新增基金", use_container_width=True, disabled=_is_locked("add_fund"))

    error_msg = st.session_state.get("new_fund_fetch_error", "")
    if error_msg:
        st.warning(error_msg)

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

    funds = service.list_funds()
    if not funds:
        st.info("暂无基金，请先录入基金信息。")
        return

    df = pd.DataFrame(funds)
    st.dataframe(df.rename(columns={"code": "代码", "name": "名称", "current_nav": "当前净值"}), use_container_width=True)

    with st.form("update_nav_form", clear_on_submit=True):
        options = { _format_fund_label(f): f["id"] for f in funds }
        selected = st.selectbox("选择基金更新净值", options=list(options.keys()))
        c1, c2 = st.columns(2)
        new_nav = c1.number_input("最新净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f")
        d = c2.date_input("更新日期", value=date.today(), key="update_date")
        submitted = st.form_submit_button("更新净值")
        if submitted:
            service.update_fund_nav(options[selected], new_nav, d.isoformat())
            st.success("净值已更新。")


def render_trades_and_chart() -> None:
    st.subheader("2) 交易记录与曲线图")
    funds = service.list_funds()
    if not funds:
        return

    analysis_basis = st.radio(
        "分析口径",
        options=["按确认日", "按申请日"],
        horizontal=True,
        help="用于交易排序、FIFO计算和买入点在图上的日期位置。",
    )
    date_field = "confirm_date" if analysis_basis == "按确认日" else "apply_date"

    options = {_format_fund_label(f): f["id"] for f in funds}
    selected_label = st.selectbox("选择基金", list(options.keys()))
    fund_id = options[selected_label]
    selected_fund = next(f for f in funds if f["id"] == fund_id)
    remaining_shares = service.get_remaining_shares(fund_id)
    summary = service.get_position_summary(fund_id)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("持仓份额", f"{summary['holding_shares']:.4f}")
    c2.metric("持仓成本", f"{summary['holding_cost']:.4f}")
    c3.metric("当前净值", f"{summary['current_nav']:.4f}")
    c4.metric("估值", f"{summary['market_value']:.4f}")
    c5.metric("浮动盈亏", f"{summary['floating_pnl']:.4f}")

    t1, t2 = st.columns(2)
    with t1:
        with st.form("buy_form", clear_on_submit=True):
            st.markdown("**买入**")
            apply_d = st.date_input("买入申请日", value=date.today(), key="buy_apply_date")
            confirm_d = st.date_input("买入确认日", value=date.today(), key="buy_confirm_date")
            auto_price = st.checkbox("使用确认日自动净值", value=True, key="buy_auto_price")
            buy_auto_nav = _fetch_nav_by_date(selected_fund["code"], confirm_d.isoformat())
            if auto_price:
                if buy_auto_nav is None:
                    st.warning("未获取到确认日净值，请切换为手动输入。")
                    price = st.number_input(
                        "买入确认净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f", key="buy_price"
                    )
                else:
                    price = buy_auto_nav
                    st.info(f"买入确认净值（自动）: {price:.4f}")
            else:
                price = st.number_input(
                    "买入确认净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f", key="buy_price"
                )
            buy_preset = st.selectbox(
                "买入份额快捷",
                ["自定义", "100", "500", "1000", "5000"],
                key=f"buy_preset_{fund_id}",
            )
            buy_default = 100.0 if buy_preset == "自定义" else float(buy_preset)
            shares = st.number_input(
                "买入份额",
                min_value=0.0001,
                value=buy_default,
                step=1.0,
                format="%.4f",
                key=f"buy_shares_{fund_id}_{buy_preset}",
            )
            amount = round(price * shares, 4)
            st.write(f"自动计算金额: **{amount}**")
            submitted = st.form_submit_button("记录买入", disabled=_is_locked("buy_tx"))
            if submitted:
                try:
                    service.add_buy(fund_id, apply_d.isoformat(), confirm_d.isoformat(), price, shares)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.success("买入记录已保存。")
                    _lock("buy_tx")

    with t2:
        with st.form("sell_form", clear_on_submit=True):
            st.markdown("**卖出（FIFO）**")
            st.caption(f"当前可卖出份额：{remaining_shares:.4f}")
            apply_d = st.date_input("卖出申请日", value=date.today(), key="sell_apply_date")
            confirm_d = st.date_input("卖出确认日", value=date.today(), key="sell_confirm_date")
            auto_price = st.checkbox("使用确认日自动净值", value=True, key="sell_auto_price")
            sell_auto_nav = _fetch_nav_by_date(selected_fund["code"], confirm_d.isoformat())
            if auto_price:
                if sell_auto_nav is None:
                    st.warning("未获取到确认日净值，请切换为手动输入。")
                    price = st.number_input(
                        "卖出确认净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f", key="sell_price"
                    )
                else:
                    price = sell_auto_nav
                    st.info(f"卖出确认净值（自动）: {price:.4f}")
            else:
                price = st.number_input(
                    "卖出确认净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f", key="sell_price"
                )
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
                format="%.4f",
                key=f"sell_shares_{fund_id}_{sell_preset}",
            )
            sell_risk = service.classify_sell_risk(remaining_shares, float(shares))
            sell_confirmed = True
            if sell_risk in ("large", "clearout"):
                tip = "清仓卖出" if sell_risk == "clearout" else "大额卖出（≥50%持仓）"
                st.warning(f"{tip}：请勾选下方确认后再提交。")
                sell_confirmed = st.checkbox("我已核对份额与价格，确认提交本次卖出", value=False, key=f"sell_confirm_{fund_id}")
            submitted = st.form_submit_button("记录卖出", disabled=_is_locked("sell_tx"))
            if submitted:
                if sell_risk in ("large", "clearout") and not sell_confirmed:
                    st.error("请先勾选确认后再提交卖出。")
                else:
                    try:
                        service.add_sell(fund_id, apply_d.isoformat(), confirm_d.isoformat(), price, shares)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.success("卖出记录已保存。")
                        _lock("sell_tx")

    filter_c1, filter_c2 = st.columns(2)
    tx_start = filter_c1.date_input("交易筛选开始日期", value=date.today().replace(day=1), key="tx_filter_start")
    tx_end = filter_c2.date_input("交易筛选结束日期", value=date.today(), key="tx_filter_end")
    tx_type_label = st.selectbox("交易类型筛选", ["全部", "仅买入", "仅卖出"], index=0)
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
        tx_df = tx_df.rename(
            columns={
                "tx_type": "交易类型",
                "apply_date": "申请日",
                "confirm_date": "确认日",
                "price": "价格",
                "shares": "份额",
                "amount": "金额",
            }
        )
        st.markdown("**交易记录**")
        st.dataframe(tx_df[["交易类型", "申请日", "确认日", "价格", "份额", "金额"]], use_container_width=True)
        csv_content = service.export_transactions_csv(fund_id, date_field=date_field)
        st.download_button(
            label="导出当前基金交易CSV",
            data=csv_content,
            file_name=f"fund_{selected_fund['code']}_transactions.csv",
            mime="text/csv",
        )

    nav_points = service.get_nav_points(fund_id)
    if not nav_points:
        return
    chart_range = st.radio(
        "图表时间范围",
        ["全部", "近1月", "近3月", "近1年"],
        horizontal=True,
        key=f"nav_chart_range_{fund_id}",
    )
    win_start, win_end = service.nav_chart_date_window(nav_points, chart_range)
    nav_filtered = service.filter_records_by_date_range(nav_points, "date", win_start, win_end)
    nav_df = pd.DataFrame(nav_filtered).sort_values("date")
    if nav_df.empty:
        st.info("当前时间范围内没有净值数据，请选择「全部」或更长区间。")
        return
    open_buys = service.get_open_buy_points(fund_id, date_field=date_field)
    open_buys = service.filter_records_by_date_range(open_buys, "date", win_start, win_end)

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

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=nav_df["date"],
            y=nav_df["nav"],
            mode="lines",
            name="净值走势",
            line={"width": 2},
        )
    )
    if open_buys:
        open_df = pd.DataFrame(open_buys)
        fig.add_trace(
            go.Scatter(
                x=open_df["date"],
                y=open_df["price"],
                mode="markers",
                name="仍持有买入点",
                marker={"color": "red", "size": 10, "symbol": "circle"},
                text=open_df["remaining_shares"].apply(lambda v: f"剩余份额: {v:.4f}"),
                hovertemplate="日期=%{x}<br>买入净值=%{y}<br>%{text}<extra></extra>",
            )
        )
    fig.update_layout(
        title=f"净值曲线与当前持仓买入点（{analysis_basis}）",
        xaxis_title="日期",
        yaxis_title="净值",
        legend_title="图例",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


overview = service.get_portfolio_overview()
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("组合总成本", f"{overview['total_cost']:.4f}")
k2.metric("组合总市值", f"{overview['total_value']:.4f}")
k3.metric("组合浮动盈亏", f"{overview['total_pnl']:.4f}")
k4.metric("组合收益率", f"{overview['pnl_ratio'] * 100:.2f}%")
k5.metric("累计买入金额", f"{overview['buy_amount']:.4f}")
k6.metric("累计卖出金额", f"{overview['sell_amount']:.4f}")
k7.metric("已实现盈亏", f"{overview['realized_pnl']:.4f}")

tab1, tab2, tab3 = st.tabs(["基金管理", "交易与图表", "组合总览"])
with tab1:
    render_fund_management()
with tab2:
    render_trades_and_chart()
with tab3:
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
            }
        )
        st.dataframe(
            summary_df[["基金代码", "基金名称", "持仓份额", "持仓成本", "持仓均价", "当前净值", "估值", "浮动盈亏"]],
            use_container_width=True,
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
        )
        bar_df = summary_df[["基金代码", "浮动盈亏"]]
        st.bar_chart(bar_df, x="基金代码", y="浮动盈亏")
        st.download_button(
            label="导出组合持仓CSV",
            data=service.export_portfolio_csv(),
            file_name="portfolio_positions.csv",
            mime="text/csv",
        )
    else:
        st.info("暂无基金数据。")

