from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fundshare.service import PortfolioService


st.set_page_config(page_title="个人基金交易记录器", layout="wide")
st.title("个人基金交易记录器")
st.caption("记录基金买卖，按FIFO抵扣份额，并在净值曲线上标注仍持有份额的买入点。")

service = PortfolioService()


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


def render_fund_management() -> None:
    st.subheader("1) 基金基础信息管理")
    if "new_fund_code" not in st.session_state:
        st.session_state["new_fund_code"] = ""
    if "new_fund_name" not in st.session_state:
        st.session_state["new_fund_name"] = ""
    if "new_fund_nav" not in st.session_state:
        st.session_state["new_fund_nav"] = 1.0
    if "new_fund_date" not in st.session_state:
        st.session_state["new_fund_date"] = date.today()

    c1, c2, c3, c4, c5 = st.columns([1.2, 1.5, 1.0, 1.1, 1.0])
    st.session_state["new_fund_code"] = c1.text_input(
        "基金代码",
        value=st.session_state["new_fund_code"],
        placeholder="如 161725",
        on_change=_auto_fill_new_fund,
    )
    st.session_state["new_fund_name"] = c2.text_input("基金名称", value=st.session_state["new_fund_name"])
    st.session_state["new_fund_nav"] = c3.number_input(
        "当前净值", min_value=0.0001, value=float(st.session_state["new_fund_nav"]), step=0.0001, format="%.4f"
    )
    st.session_state["new_fund_date"] = c4.date_input(
        "净值日期", value=st.session_state["new_fund_date"], on_change=_auto_fill_new_fund
    )
    if c5.button("手动重新获取", use_container_width=True):
        _auto_fill_new_fund()

    error_msg = st.session_state.get("new_fund_fetch_error", "")
    if error_msg:
        st.warning(error_msg)

    if st.button("新增基金"):
        code = st.session_state["new_fund_code"]
        name = st.session_state["new_fund_name"]
        nav = float(st.session_state["new_fund_nav"])
        nav_date = st.session_state["new_fund_date"]
        if not code.strip() or not name.strip():
            st.error("基金代码和名称不能为空。")
        else:
            service.add_fund(code, name, nav, nav_date.isoformat())
            st.success("基金已新增。")
            st.session_state["new_fund_code"] = ""
            st.session_state["new_fund_name"] = ""
            st.session_state["new_fund_nav"] = 1.0
            st.session_state["new_fund_date"] = date.today()

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

    options = {_format_fund_label(f): f["id"] for f in funds}
    selected_label = st.selectbox("选择基金", list(options.keys()))
    fund_id = options[selected_label]

    t1, t2 = st.columns(2)
    with t1:
        with st.form("buy_form", clear_on_submit=True):
            st.markdown("**买入**")
            d = st.date_input("买入日期", value=date.today(), key="buy_date")
            price = st.number_input("买入净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f")
            shares = st.number_input("买入份额", min_value=0.0001, value=100.0, step=1.0, format="%.4f")
            amount = round(price * shares, 4)
            st.write(f"自动计算金额: **{amount}**")
            submitted = st.form_submit_button("记录买入")
            if submitted:
                service.add_buy(fund_id, d.isoformat(), price, shares)
                st.success("买入记录已保存。")

    with t2:
        with st.form("sell_form", clear_on_submit=True):
            st.markdown("**卖出（FIFO）**")
            d = st.date_input("卖出日期", value=date.today(), key="sell_date")
            price = st.number_input("卖出净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f", key="sell_price")
            shares = st.number_input("卖出份额", min_value=0.0001, value=100.0, step=1.0, format="%.4f", key="sell_shares")
            submitted = st.form_submit_button("记录卖出")
            if submitted:
                try:
                    service.add_sell(fund_id, d.isoformat(), price, shares)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.success("卖出记录已保存。")

    transactions = service.get_transactions(fund_id)
    if transactions:
        tx_df = pd.DataFrame(transactions)
        tx_df = tx_df.rename(
            columns={
                "tx_type": "交易类型",
                "date": "日期",
                "price": "价格",
                "shares": "份额",
                "amount": "金额",
            }
        )
        st.markdown("**交易记录**")
        st.dataframe(tx_df[["交易类型", "日期", "价格", "份额", "金额"]], use_container_width=True)

    nav_points = service.get_nav_points(fund_id)
    if not nav_points:
        return
    nav_df = pd.DataFrame(nav_points).sort_values("date")
    open_buys = service.get_open_buy_points(fund_id)

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
        title="净值曲线与当前持仓买入点",
        xaxis_title="日期",
        yaxis_title="净值",
        legend_title="图例",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


render_fund_management()
st.divider()
render_trades_and_chart()

