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
    add_clicked = c2.button("按代码自动新增基金", use_container_width=True)

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
            shares = st.number_input("买入份额", min_value=0.0001, value=100.0, step=1.0, format="%.4f")
            amount = round(price * shares, 4)
            st.write(f"自动计算金额: **{amount}**")
            submitted = st.form_submit_button("记录买入")
            if submitted:
                try:
                    service.add_buy(fund_id, apply_d.isoformat(), confirm_d.isoformat(), price, shares)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.success("买入记录已保存。")

    with t2:
        with st.form("sell_form", clear_on_submit=True):
            st.markdown("**卖出（FIFO）**")
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
            shares = st.number_input("卖出份额", min_value=0.0001, value=100.0, step=1.0, format="%.4f", key="sell_shares")
            submitted = st.form_submit_button("记录卖出")
            if submitted:
                try:
                    service.add_sell(fund_id, apply_d.isoformat(), confirm_d.isoformat(), price, shares)
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.success("卖出记录已保存。")

    transactions = service.get_transactions(fund_id, date_field=date_field)
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
    nav_df = pd.DataFrame(nav_points).sort_values("date")
    open_buys = service.get_open_buy_points(fund_id, date_field=date_field)

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


render_fund_management()
st.divider()
render_trades_and_chart()
st.divider()
st.subheader("3) 多基金持仓对比")
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
    bar_df = summary_df[["基金代码", "浮动盈亏"]]
    st.bar_chart(bar_df, x="基金代码", y="浮动盈亏")
else:
    st.info("暂无基金数据。")

