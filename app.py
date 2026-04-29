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
        "- **基金**：新增代码、更新净值、无仓删基\n"
        "- **交易**：买卖、导入、单基净值图\n"
        "- **组合**：总览指标、持仓表与导出"
    )
    _dd = os.environ.get("DATA_DIR", "").strip()
    st.caption("数据目录：" + (_dd if _dd else "默认 `data/`，可用环境变量 `DATA_DIR`"))
    st.divider()
st.title("个人基金交易记录器")
st.caption("记录基金买卖，按 FIFO 抵扣份额；净值曲线可叠加买入点与多基对比。")

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
            f"{f['code']} - {f['name']}  |  持有收益 {hold_pnl:.4f}  |  收益率 {hold_ratio:.2f}%  |  累计盈亏 {cum_pnl:.4f}"
        )
        with st.expander(exp_title, expanded=False):
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("基金代码", str(f["code"]))
            k2.metric("持有份额", f"{float(s['holding_shares']):.4f}")
            k3.metric("持有收益", f"{hold_pnl:.4f}")
            k4.metric("持有收益率", f"{hold_ratio:.2f}%")
            k5.metric("累计盈亏", f"{cum_pnl:.4f}")

            nav_points = service.get_nav_points(f["id"])
            if nav_points:
                nav_df = pd.DataFrame(nav_points).sort_values("date")
                fig_nav = go.Figure()
                fig_nav.add_trace(
                    go.Scatter(
                        x=nav_df["date"],
                        y=nav_df["nav"],
                        mode="lines",
                        name="业绩走势(净值)",
                        line={"width": 2},
                    )
                )
                fig_nav.update_layout(
                    title="业绩走势",
                    xaxis_title="日期",
                    yaxis_title="净值",
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
                    )[["类型", "申请日", "确认日", "价格", "份额", "金额", "手续费"]],
                    use_container_width=True,
                    hide_index=True,
                    height=min(300, 52 + len(tx_df) * 36),
                )


def render_maintenance() -> None:
    st.subheader("基金维护")
    st.caption("用于基金新增、净值更新与删除；不会影响「基金管理」展示逻辑。")

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

    st.dataframe(
        pd.DataFrame(funds).rename(columns={"code": "代码", "name": "名称", "current_nav": "当前净值"}),
        use_container_width=True,
        hide_index=True,
        height=min(320, 52 + len(funds) * 36),
    )

    with st.form("update_nav_form", clear_on_submit=True):
        options = {_format_fund_label(f): f["id"] for f in funds}
        selected = st.selectbox("选择基金更新净值", options=list(options.keys()))
        nc1, nc2 = st.columns(2)
        new_nav = nc1.number_input("最新净值", min_value=0.0001, value=1.0, step=0.0001, format="%.4f")
        d = nc2.date_input("更新日期", value=date.today(), key="maint_update_date")
        submitted = st.form_submit_button("更新净值")
        if submitted:
            service.update_fund_nav(options[selected], new_nav, d.isoformat())
            st.success("净值已更新。")
            st.rerun()

    with st.expander("删除基金（无持仓时）"):
        del_opts = {_format_fund_label(f): f["id"] for f in funds}
        del_pick = st.selectbox("选择要删除的基金", options=list(del_opts.keys()), key="maint_fund_delete_pick")
        if st.button("确认删除该基金及其历史净值与交易", key="maint_fund_delete_btn"):
            try:
                service.delete_fund(del_opts[del_pick])
            except DomainError as e:
                st.error(str(e))
            else:
                st.success("已删除。")
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
    m1.metric("持仓份额", f"{summary['holding_shares']:.4f}")
    m2.metric("持仓成本", f"{summary['holding_cost']:.4f}")
    m3.metric("当前净值", f"{summary['current_nav']:.4f}")
    m4.metric("估值", f"{summary['market_value']:.4f}")
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("浮动盈亏", f"{summary['floating_pnl']:.4f}")
    m6.metric("加权持仓天数", f"{summary['avg_holding_days']:.1f}", help="按剩余份额加权")
    m7.metric("最早买入天数", f"{summary['first_lot_age_days']:.1f}")
    m8.metric("简易年化", f"{summary['annualized_simple_ratio'] * 100:.2f}%", help="浮盈/成本，按加权持仓天数线性折算年率")

    t1, t2 = st.columns(2)
    with t1:
        with st.container(border=True):
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
                buy_fee = st.number_input(
                    "手续费（可选）", min_value=0.0, value=0.0, step=0.01, format="%.4f", key=f"buy_fee_{fund_id}"
                )
                amount = round(price * shares, 4)
                st.write(f"自动计算金额: **{amount}**")
                submitted = st.form_submit_button("记录买入", disabled=_is_locked("buy_tx"))
                if submitted:
                    try:
                        service.add_buy(fund_id, apply_d.isoformat(), confirm_d.isoformat(), price, shares, buy_fee)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        st.success("买入记录已保存。")
                        _lock("buy_tx")

    with t2:
        with st.container(border=True):
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
                sell_fee = st.number_input(
                    "手续费（可选）", min_value=0.0, value=0.0, step=0.01, format="%.4f", key=f"sell_fee_{fund_id}"
                )
                sell_risk = service.classify_sell_risk(remaining_shares, float(shares))
                sell_confirmed = True
                if sell_risk in ("large", "clearout"):
                    tip = "清仓卖出" if sell_risk == "clearout" else "大额卖出（≥50%持仓）"
                    st.warning(f"{tip}：请勾选下方确认后再提交。")
                    sell_confirmed = st.checkbox(
                        "我已核对份额与价格，确认提交本次卖出", value=False, key=f"sell_confirm_{fund_id}"
                    )
                submitted = st.form_submit_button("记录卖出", disabled=_is_locked("sell_tx"))
                if submitted:
                    if sell_risk in ("large", "clearout") and not sell_confirmed:
                        st.error("请先勾选确认后再提交卖出。")
                    else:
                        try:
                            service.add_sell(
                                fund_id, apply_d.isoformat(), confirm_d.isoformat(), price, shares, sell_fee
                            )
                        except ValueError as e:
                            st.error(str(e))
                        else:
                            st.success("卖出记录已保存。")
                            _lock("sell_tx")

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
            tx_df[["交易类型", "申请日", "确认日", "价格", "份额", "金额", "手续费"]],
            use_container_width=True,
            hide_index=True,
            height=min(400, 52 + len(transactions) * 36),
        )
        csv_content = service.export_transactions_csv(fund_id, date_field=date_field)
        st.download_button(
            label="导出当前基金交易CSV",
            data=csv_content,
            file_name=f"fund_{selected_fund['code']}_transactions.csv",
            mime="text/csv",
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
            with j2:
                sample_payload = json.dumps(
                    {
                        "fund_code": selected_fund["code"],
                        "transactions": [
                            {
                                "tx_type": "buy",
                                "apply_date": "2026-01-02",
                                "confirm_date": "2026-01-03",
                                "price": 1.0,
                                "shares": 10.0,
                                "fee": 0.5,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                st.download_button(
                    "下载示例",
                    sample_payload,
                    file_name=f"import_sample_{selected_fund['code']}.json",
                    mime="application/json",
                )
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
            with c2:
                csv_template = (
                    "tx_type,apply_date,confirm_date,price,shares,amount,fee\n"
                    "buy,2026-01-02,2026-01-03,1.0,100.0,100.0,0\n"
                )
                st.download_button(
                    "下载 CSV 模板",
                    csv_template,
                    file_name=f"import_template_{selected_fund['code']}.csv",
                    mime="text/csv",
                    key=f"tx_csv_tpl_{fund_id}",
                )
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
    if not nav_points:
        return
    st.markdown("##### 净值曲线")
    chart_range = st.radio(
        "区间",
        ["全部", "近1月", "近3月", "近1年"],
        horizontal=True,
        index=0,
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

    plotly_tpl = "plotly_dark" if st.session_state.get("fundshare_plotly_dark") else "plotly_white"
    show_nav_dod = st.checkbox(
        "显示相邻净值点涨跌幅（右轴，%）",
        value=False,
        key=f"nav_dod_{fund_id}",
    )
    nav_pct = (nav_df["nav"].astype(float).pct_change() * 100.0).fillna(0.0)

    if show_nav_dod:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=nav_df["date"],
                y=nav_df["nav"],
                mode="lines",
                name="净值走势",
                line={"width": 2},
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=nav_df["date"],
                y=nav_pct,
                mode="lines",
                name="点间涨跌%",
                line={"dash": "dot", "width": 1},
            ),
            secondary_y=True,
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
                ),
                secondary_y=False,
            )
        fig.update_layout(
            title=f"净值曲线与当前持仓买入点（{analysis_basis}）",
            legend_title="图例",
            template=plotly_tpl,
            xaxis_rangeslider_visible=True,
        )
        fig.update_xaxes(title_text="日期")
        fig.update_yaxes(title_text="净值", secondary_y=False)
        fig.update_yaxes(title_text="环比涨跌幅 %", secondary_y=True)
    else:
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
            template=plotly_tpl,
            xaxis_rangeslider_visible=True,
        )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("多基金净值对比（可选）")
    code_opts = [f["code"] for f in funds]
    mc1, mc2 = st.columns([4, 1])
    with mc1:
        cmp_pick = st.multiselect(
            "选择多只基金（区间内首点归一为 100）",
            options=code_opts,
            default=[],
            key="nav_multi_compare",
        )
    with mc2:
        st.write("")  # spacer
        st.write("")
        if st.button("加入当前基金", key="nav_cmp_add_current", help="把上方选中的基金加入对比列表"):
            cur = str(selected_fund["code"])
            prev = list(st.session_state.get("nav_multi_compare") or [])
            if cur not in prev:
                st.session_state["nav_multi_compare"] = prev + [cur]
                st.rerun()
    cmp_range = st.radio(
        "对比图时间范围",
        ["全部", "近1月", "近3月", "近1年"],
        horizontal=True,
        key="nav_cmp_range",
    )
    if len(cmp_pick) >= 2:
        all_pts: list[dict] = []
        fid_by_code = {f["code"]: f["id"] for f in funds}
        for c in cmp_pick:
            all_pts.extend(service.get_nav_points(fid_by_code[c]))
        w0, w1 = service.nav_chart_date_window(all_pts, cmp_range)
        fig_m = go.Figure()
        for c in cmp_pick:
            fid = fid_by_code[c]
            pts = service.get_nav_points(fid)
            filt = service.filter_records_by_date_range(pts, "date", w0, w1)
            if not filt:
                continue
            nd = pd.DataFrame(filt).sort_values("date")
            b = float(nd["nav"].iloc[0])
            if b <= 0:
                continue
            y = nd["nav"].astype(float) / b * 100.0
            fn = next(f["name"] for f in funds if f["code"] == c)
            fig_m.add_trace(go.Scatter(x=nd["date"], y=y, mode="lines", name=f"{c} {fn}"))
        if fig_m.data:
            fig_m.update_layout(
                title="多基金净值对比（首点=100）",
                xaxis_title="日期",
                yaxis_title="相对净值",
                template=plotly_tpl,
                legend_title="基金",
                xaxis_rangeslider_visible=True,
            )
            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.info("所选基金在范围内暂无净值数据。")


tab1, tab2, tab3, tab4 = st.tabs(["组合总览", "基金管理", "交易与净值", "维护"])
with tab1:
    overview = service.get_portfolio_overview()
    st.subheader("组合概览")
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("总成本", f"{overview['total_cost']:.4f}")
    o2.metric("总市值", f"{overview['total_value']:.4f}")
    o3.metric("浮动盈亏", f"{overview['total_pnl']:.4f}")
    o4.metric("组合收益率", f"{overview['pnl_ratio'] * 100:.2f}%")
    o5, o6, o7, o8 = st.columns(4)
    o5.metric("累计买入", f"{overview['buy_amount']:.4f}")
    o6.metric("累计卖出", f"{overview['sell_amount']:.4f}")
    o7.metric("已实现盈亏", f"{overview['realized_pnl']:.4f}")
    o8.metric("累计手续费", f"{overview['total_fees']:.4f}")
    st.caption(f"扣费后已实现盈亏：**{overview['realized_pnl_after_fees']:.4f}**")
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
        st.download_button(
            label="导出组合持仓CSV",
            data=service.export_portfolio_csv(),
            file_name="portfolio_positions.csv",
            mime="text/csv",
        )
    else:
        st.info("暂无基金数据。")
with tab2:
    render_fund_management()
with tab3:
    render_trades_and_chart()
with tab4:
    render_maintenance()

