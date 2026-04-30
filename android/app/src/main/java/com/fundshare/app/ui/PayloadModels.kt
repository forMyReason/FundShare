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
