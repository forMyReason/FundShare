package com.fundshare.app.ui

import org.json.JSONArray
import org.json.JSONObject

data class OverviewUi(
    val totalCost: Double,
    val totalValue: Double,
    val totalPnl: Double,
    val pnlRatio: Double,
    val buyAmount: Double,
    val sellAmount: Double,
    val realizedPnl: Double,
    val totalFees: Double,
    val realizedPnlAfterFees: Double,
)

data class PositionUi(
    val code: String,
    val name: String,
    val holdingShares: Double,
    val holdingCost: Double,
    val marketValue: Double,
    val floatingPnl: Double,
    val currentNav: Double,
    val avgHoldingDays: Double,
    val annualizedSimpleRatio: Double,
)

data class FundUi(
    val id: Int,
    val code: String,
    val name: String,
    val currentNav: Double,
)

data class TransactionUi(
    val id: Int,
    val fundId: Int,
    val fundCode: String,
    val fundName: String,
    val txType: String,
    val applyDate: String,
    val confirmDate: String,
    val shares: Double,
    val amount: Double,
    val price: Double,
    val fee: Double,
)

data class FullPayload(
    val version: String,
    val dataDir: String,
    val overview: OverviewUi?,
    val positions: List<PositionUi>,
    val funds: List<FundUi>,
    val transactions: List<TransactionUi>,
    val error: String?,
)

data class ChartWindowUi(val start: String, val end: String)

data class SellableLotUi(
    val buyId: Int,
    val date: String,
    val price: Double,
    val originalShares: Double,
    val remainingShares: Double,
)

data class NavPointUi(val date: String, val nav: Double)

data class BuyPointUi(
    val date: String,
    val price: Double,
    val buyCount: Int,
    val originalShares: Double,
    val remainingShares: Double,
)

data class SellPointUi(val date: String, val price: Double, val shares: Double)

data class TradesPayload(
    val funds: List<FundUi>,
    val selectedFundId: Int,
    val selectedFund: FundUi?,
    val chartRange: String,
    val txType: String,
    val txStart: String,
    val txEnd: String,
    val summary: PositionUi?,
    val remainingShares: Double,
    val sellableLots: List<SellableLotUi>,
    val transactions: List<TransactionUi>,
    val navPoints: List<NavPointUi>,
    val buyPoints: List<BuyPointUi>,
    val sellPoints: List<SellPointUi>,
    val calendarGaps: List<List<Any>>,
    val chartWindow: ChartWindowUi?,
    val warning: String,
    val error: String?,
)

data class RpcResponse(
    val ok: Boolean,
    val message: String,
    val error: String,
    val dataJson: JSONObject?,
)

private fun JSONObject.optDoubleSafe(key: String, default: Double = 0.0): Double =
    when {
        !has(key) || isNull(key) -> default
        else -> optDouble(key, default)
    }

fun parseFullPayload(json: String): FullPayload {
    val root = JSONObject(json)
    val err: String? =
        when {
            !root.has("error") || root.isNull("error") -> null
            else ->
                root.optString("error", "")
                    .takeIf { it.isNotBlank() && !it.equals("null", ignoreCase = true) }
        }

    val overview: OverviewUi? = if (root.has("overview") && !root.isNull("overview")) {
        val o = root.getJSONObject("overview")
        OverviewUi(
            totalCost = o.optDoubleSafe("total_cost"),
            totalValue = o.optDoubleSafe("total_value"),
            totalPnl = o.optDoubleSafe("total_pnl"),
            pnlRatio = o.optDoubleSafe("pnl_ratio"),
            buyAmount = o.optDoubleSafe("buy_amount"),
            sellAmount = o.optDoubleSafe("sell_amount"),
            realizedPnl = o.optDoubleSafe("realized_pnl"),
            totalFees = o.optDoubleSafe("total_fees"),
            realizedPnlAfterFees = o.optDoubleSafe("realized_pnl_after_fees"),
        )
    } else {
        null
    }

    val positions = mutableListOf<PositionUi>()
    val pa = root.optJSONArray("positions") ?: JSONArray()
    for (i in 0 until pa.length()) {
        val p = pa.getJSONObject(i)
        positions.add(
            PositionUi(
                code = p.optString("code"),
                name = p.optString("name"),
                holdingShares = p.optDoubleSafe("holding_shares"),
                holdingCost = p.optDoubleSafe("holding_cost"),
                marketValue = p.optDoubleSafe("market_value"),
                floatingPnl = p.optDoubleSafe("floating_pnl"),
                currentNav = p.optDoubleSafe("current_nav"),
                avgHoldingDays = p.optDoubleSafe("avg_holding_days"),
                annualizedSimpleRatio = p.optDoubleSafe("annualized_simple_ratio"),
            ),
        )
    }

    val funds = mutableListOf<FundUi>()
    val fa = root.optJSONArray("funds") ?: JSONArray()
    for (i in 0 until fa.length()) {
        val f = fa.getJSONObject(i)
        funds.add(
            FundUi(
                id = f.optInt("id", 0),
                code = f.optString("code"),
                name = f.optString("name"),
                currentNav = f.optDoubleSafe("current_nav"),
            ),
        )
    }

    val txs = mutableListOf<TransactionUi>()
    val ta = root.optJSONArray("transactions") ?: JSONArray()
    for (i in 0 until ta.length()) {
        val t = ta.getJSONObject(i)
        txs.add(
            TransactionUi(
                id = t.optInt("id", 0),
                fundId = t.optInt("fund_id", 0),
                fundCode = t.optString("fund_code"),
                fundName = t.optString("fund_name"),
                txType = t.optString("tx_type"),
                applyDate = t.optString("apply_date"),
                confirmDate = t.optString("confirm_date"),
                shares = t.optDoubleSafe("shares"),
                amount = t.optDoubleSafe("amount"),
                price = t.optDoubleSafe("price"),
                fee = t.optDoubleSafe("fee"),
            ),
        )
    }

    return FullPayload(
        version = root.optString("fundshare_version"),
        dataDir = root.optString("data_dir"),
        overview = overview,
        positions = positions,
        funds = funds,
        transactions = txs,
        error = err,
    )
}

fun parseRpcResponse(json: String): RpcResponse {
    val o = JSONObject(json)
    val data = if (o.has("data") && !o.isNull("data")) o.getJSONObject("data") else null
    return RpcResponse(
        ok = o.optBoolean("ok", false),
        message = o.optString("message", ""),
        error = o.optString("error", ""),
        dataJson = data,
    )
}

fun parseTradesPayload(json: String): TradesPayload {
    val root = JSONObject(json)
    val err: String? =
        if (!root.has("error") || root.isNull("error")) null
        else root.optString("error", "").takeIf { it.isNotBlank() }

    val funds = mutableListOf<FundUi>()
    val fundsArr = root.optJSONArray("funds") ?: JSONArray()
    for (i in 0 until fundsArr.length()) {
        val f = fundsArr.getJSONObject(i)
        funds.add(
            FundUi(
                id = f.optInt("id", 0),
                code = f.optString("code"),
                name = f.optString("name"),
                currentNav = f.optDoubleSafe("current_nav"),
            ),
        )
    }

    val selectedFundObj = if (root.has("selected_fund") && !root.isNull("selected_fund")) root.getJSONObject("selected_fund") else null
    val selectedFund =
        selectedFundObj?.let {
            FundUi(
                id = it.optInt("id", 0),
                code = it.optString("code"),
                name = it.optString("name"),
                currentNav = it.optDoubleSafe("current_nav"),
            )
        }

    val summaryObj = if (root.has("summary") && !root.isNull("summary")) root.getJSONObject("summary") else null
    val summary =
        summaryObj?.let {
            PositionUi(
                code = selectedFund?.code ?: "",
                name = selectedFund?.name ?: "",
                holdingShares = it.optDoubleSafe("holding_shares"),
                holdingCost = it.optDoubleSafe("holding_cost"),
                marketValue = it.optDoubleSafe("market_value"),
                floatingPnl = it.optDoubleSafe("floating_pnl"),
                currentNav = it.optDoubleSafe("current_nav"),
                avgHoldingDays = it.optDoubleSafe("avg_holding_days"),
                annualizedSimpleRatio = it.optDoubleSafe("annualized_simple_ratio"),
            )
        }

    val lots = mutableListOf<SellableLotUi>()
    val la = root.optJSONArray("sellable_lots") ?: JSONArray()
    for (i in 0 until la.length()) {
        val l = la.getJSONObject(i)
        lots.add(
            SellableLotUi(
                buyId = l.optInt("buy_id", 0),
                date = l.optString("date"),
                price = l.optDoubleSafe("price"),
                originalShares = l.optDoubleSafe("original_shares"),
                remainingShares = l.optDoubleSafe("remaining_shares"),
            ),
        )
    }

    val txs = mutableListOf<TransactionUi>()
    val ta = root.optJSONArray("transactions") ?: JSONArray()
    for (i in 0 until ta.length()) {
        val t = ta.getJSONObject(i)
        txs.add(
            TransactionUi(
                id = t.optInt("id", 0),
                fundId = t.optInt("fund_id", 0),
                fundCode = t.optString("fund_code"),
                fundName = t.optString("fund_name"),
                txType = t.optString("tx_type"),
                applyDate = t.optString("apply_date"),
                confirmDate = t.optString("confirm_date"),
                shares = t.optDoubleSafe("shares"),
                amount = t.optDoubleSafe("amount"),
                price = t.optDoubleSafe("price"),
                fee = t.optDoubleSafe("fee"),
            ),
        )
    }

    val nav = mutableListOf<NavPointUi>()
    val na = root.optJSONArray("nav_points") ?: JSONArray()
    for (i in 0 until na.length()) {
        val n = na.getJSONObject(i)
        nav.add(NavPointUi(date = n.optString("date"), nav = n.optDoubleSafe("nav")))
    }

    val buys = mutableListOf<BuyPointUi>()
    val ba = root.optJSONArray("buy_points") ?: JSONArray()
    for (i in 0 until ba.length()) {
        val b = ba.getJSONObject(i)
        buys.add(
            BuyPointUi(
                date = b.optString("date"),
                price = b.optDoubleSafe("price"),
                buyCount = b.optInt("buy_count", 0),
                originalShares = b.optDoubleSafe("original_shares"),
                remainingShares = b.optDoubleSafe("remaining_shares"),
            ),
        )
    }

    val sells = mutableListOf<SellPointUi>()
    val sa = root.optJSONArray("sell_points") ?: JSONArray()
    for (i in 0 until sa.length()) {
        val s = sa.getJSONObject(i)
        sells.add(
            SellPointUi(
                date = s.optString("date"),
                price = s.optDoubleSafe("price"),
                shares = s.optDoubleSafe("shares"),
            ),
        )
    }

    val gaps = mutableListOf<List<Any>>()
    val ga = root.optJSONArray("calendar_gaps") ?: JSONArray()
    for (i in 0 until ga.length()) {
        val row = ga.optJSONArray(i) ?: JSONArray()
        val tuple = mutableListOf<Any>()
        for (j in 0 until row.length()) {
            tuple.add(row.get(j))
        }
        gaps.add(tuple)
    }

    val windowObj = if (root.has("chart_window") && !root.isNull("chart_window")) root.getJSONObject("chart_window") else null
    val chartWindow =
        windowObj?.let {
            ChartWindowUi(
                start = it.optString("start"),
                end = it.optString("end"),
            )
        }

    return TradesPayload(
        funds = funds,
        selectedFundId = root.optInt("selected_fund_id", funds.firstOrNull()?.id ?: 0),
        selectedFund = selectedFund,
        chartRange = root.optString("chart_range", "近1年"),
        txType = root.optString("tx_type", "all"),
        txStart = root.optString("tx_start", ""),
        txEnd = root.optString("tx_end", ""),
        summary = summary,
        remainingShares = root.optDoubleSafe("remaining_shares"),
        sellableLots = lots,
        transactions = txs,
        navPoints = nav,
        buyPoints = buys,
        sellPoints = sells,
        calendarGaps = gaps,
        chartWindow = chartWindow,
        warning = root.optString("warning", ""),
        error = err,
    )
}
