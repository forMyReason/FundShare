package com.fundshare.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.util.Locale

private fun fmtMoney(v: Double): String = String.format(Locale.US, "%.2f", v)

private fun fmt4(v: Double): String = String.format(Locale.US, "%.4f", v)

private fun pnlColor(v: Double): Color =
    when {
        v > 1e-6 -> Color(0xFF2E7D32)
        v < -1e-6 -> Color(0xFFC62828)
        else -> Color.Unspecified
    }

@Composable
private fun TradeMiniStat(label: String, value: String, color: Color = Color.Unspecified) {
    val c = if (color == Color.Unspecified) MaterialTheme.colorScheme.onSurface else color
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, color = c)
    }
}

private fun jsonArgs(map: Map<String, Any>): String {
    val o = JSONObject()
    map.forEach { (k, v) ->
        when (v) {
            is Int, is Long, is Double, is Float, is Boolean, is String -> o.put(k, v)
            is List<*> -> o.put(k, JSONArray(v))
            else -> o.put(k, v.toString())
        }
    }
    return o.toString()
}

@Composable
fun TradesTabContent(
    fullPayload: FullPayload,
    fetchPayload: suspend (String) -> TradesPayload,
    tradesRpc: suspend (String, String) -> RpcResponse,
    onUserMessage: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val funds = fullPayload.funds
    var selectedFundId by remember { mutableStateOf(funds.firstOrNull()?.id ?: 0) }
    var txStart by remember { mutableStateOf(LocalDate.now().withDayOfMonth(1).toString()) }
    var txEnd by remember { mutableStateOf(LocalDate.now().toString()) }
    var txType by remember { mutableStateOf("all") }
    var chartRange by remember { mutableStateOf("近1年") }
    var showAdvanced by remember { mutableStateOf(false) }
    var payload by remember { mutableStateOf<TradesPayload?>(null) }
    var loading by remember { mutableStateOf(false) }

    var buyConfirmDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var buyMode by remember { mutableStateOf("price") } // price | amount
    var buyPrice by remember { mutableStateOf("1.0") }
    var buyShares by remember { mutableStateOf("100") }
    var buyAmount by remember { mutableStateOf("100") }
    var buyFee by remember { mutableStateOf("0") }

    var sellConfirmDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var sellMode by remember { mutableStateOf("lots") } // fifo | lots
    var sellEntryMode by remember { mutableStateOf("price") } // price | amount
    var sellPrice by remember { mutableStateOf("1.0") }
    var sellShares by remember { mutableStateOf("100") }
    var sellAmount by remember { mutableStateOf("100") }
    var sellFee by remember { mutableStateOf("0") }
    var sellRiskConfirmed by remember { mutableStateOf(false) }

    var importJsonText by remember { mutableStateOf("") }
    var importCsvText by remember { mutableStateOf("") }
    var exportedCsv by remember { mutableStateOf("") }

    val selectedLotChecks = remember { mutableStateMapOf<Int, Boolean>() }
    val selectedLotShares = remember { mutableStateMapOf<Int, String>() }

    fun reload() {
        if (selectedFundId <= 0) return
        scope.launch {
            loading = true
            val args =
                jsonArgs(
                    mapOf(
                        "fund_id" to selectedFundId,
                        "tx_start" to txStart,
                        "tx_end" to txEnd,
                        "tx_type" to txType,
                        "chart_range" to chartRange,
                    ),
                )
            payload = fetchPayload(args)
            loading = false
        }
    }

    LaunchedEffect(selectedFundId) {
        if (selectedFundId > 0) reload()
    }

    if (funds.isEmpty()) {
        Text("请先在「基金管理」中新增基金。")
        return
    }

    val p = payload
    val summary = p?.summary
    val remaining = p?.remainingShares ?: 0.0
    val sellLots = p?.sellableLots ?: emptyList()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("交易与净值", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(
                "优先完成买入/卖出记录；其余分析功能可按需展开。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (loading) Text("加载中…", color = MaterialTheme.colorScheme.primary)
            p?.error?.takeIf { it.isNotBlank() }?.let {
                Text("错误：$it", color = MaterialTheme.colorScheme.error)
            }
        }
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("当前基金", fontWeight = FontWeight.SemiBold)
                    Text("仅按确认日口径", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        funds.forEach { f ->
                            FilterChip(
                                selected = selectedFundId == f.id,
                                onClick = { selectedFundId = f.id },
                                label = { Text("${f.code} ${f.name.take(4)}") },
                            )
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { reload() }, modifier = Modifier.weight(1f)) { Text("刷新") }
                        FilterChip(
                            selected = showAdvanced,
                            onClick = { showAdvanced = !showAdvanced },
                            label = { Text(if (showAdvanced) "收起扩展功能" else "展开扩展功能") },
                        )
                    }
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("持仓快照", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    if (summary == null) {
                        Text("暂无快照数据。")
                    } else {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                            TradeMiniStat("持仓份额", String.format(Locale.US, "%.2f", summary.holdingShares))
                            TradeMiniStat("持仓成本", String.format(Locale.US, "%.2f", summary.holdingCost))
                            TradeMiniStat("当前净值", String.format(Locale.US, "%.4f", summary.currentNav))
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                            TradeMiniStat("估值", String.format(Locale.US, "%.2f", summary.marketValue))
                            TradeMiniStat("浮动盈亏", String.format(Locale.US, "%.2f", summary.floatingPnl), pnlColor(summary.floatingPnl))
                            TradeMiniStat("简易年化", String.format(Locale.US, "%.2f%%", summary.annualizedSimpleRatio * 100))
                        }
                    }
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("买入", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    OutlinedTextField(buyConfirmDate, { buyConfirmDate = it }, label = { Text("买入确认日（YYYY-MM-DD）") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = buyMode == "price", onClick = { buyMode = "price" }, label = { Text("按净值+份额") })
                        FilterChip(selected = buyMode == "amount", onClick = { buyMode = "amount" }, label = { Text("按金额+份额") })
                    }
                    if (buyMode == "price") {
                        OutlinedTextField(buyPrice, { buyPrice = it }, label = { Text("买入确认净值") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(buyShares, { buyShares = it }, label = { Text("买入份额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        val amt = (buyPrice.toDoubleOrNull() ?: 0.0) * (buyShares.toDoubleOrNull() ?: 0.0)
                        Text("本次买入金额：${String.format(Locale.US, "%.2f", amt)}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        OutlinedTextField(buyAmount, { buyAmount = it }, label = { Text("买入金额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(buyShares, { buyShares = it }, label = { Text("买入份额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        val calc = (buyAmount.toDoubleOrNull() ?: 0.0) / maxOf(1e-9, (buyShares.toDoubleOrNull() ?: 0.0))
                        Text("自动计算净值：${String.format(Locale.US, "%.6f", calc)}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    OutlinedTextField(buyFee, { buyFee = it }, label = { Text("手续费（可选）") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Button(
                        onClick = {
                            val sh = buyShares.toDoubleOrNull() ?: 0.0
                            val fee = buyFee.toDoubleOrNull() ?: 0.0
                            val price =
                                if (buyMode == "price") (buyPrice.toDoubleOrNull() ?: 0.0)
                                else (buyAmount.toDoubleOrNull() ?: 0.0) / maxOf(1e-9, sh)
                            if (buyConfirmDate.isBlank() || sh <= 0.0 || price <= 0.0) {
                                onUserMessage("请输入有效的买入确认日、份额和净值。")
                                return@Button
                            }
                            scope.launch {
                                val r =
                                    tradesRpc(
                                        "add_buy",
                                        jsonArgs(
                                            mapOf(
                                                "fund_id" to selectedFundId,
                                                "confirm_date" to buyConfirmDate,
                                                "price" to price,
                                                "shares" to sh,
                                                "fee" to fee,
                                            ),
                                        ),
                                    )
                                onUserMessage(if (r.ok) r.message else r.error)
                                if (r.ok) reload()
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("记录买入") }
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("卖出", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("当前可卖出份额：${String.format(Locale.US, "%.2f", remaining)}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    OutlinedTextField(sellConfirmDate, { sellConfirmDate = it }, label = { Text("卖出确认日（YYYY-MM-DD）") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = sellMode == "fifo", onClick = { sellMode = "fifo" }, label = { Text("FIFO 自动") })
                        FilterChip(selected = sellMode == "lots", onClick = { sellMode = "lots" }, label = { Text("指定批次") })
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = sellEntryMode == "price", onClick = { sellEntryMode = "price" }, label = { Text("按净值+份额") })
                        FilterChip(selected = sellEntryMode == "amount", onClick = { sellEntryMode = "amount" }, label = { Text("按金额+份额") })
                    }
                    if (sellMode == "fifo") {
                        OutlinedTextField(sellShares, { sellShares = it }, label = { Text("卖出份额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    } else {
                        Text("选择抵扣批次：", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Column(Modifier.height(130.dp).verticalScroll(rememberScrollState())) {
                            sellLots.forEach { lot ->
                                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                                    val checked = selectedLotChecks[lot.buyId] ?: false
                                    Checkbox(
                                        checked = checked,
                                        onCheckedChange = {
                                            selectedLotChecks[lot.buyId] = it
                                            if (it && selectedLotShares[lot.buyId] == null) {
                                                selectedLotShares[lot.buyId] = String.format(Locale.US, "%.2f", lot.remainingShares)
                                            }
                                        },
                                    )
                                    Text("买入#${lot.buyId} ${lot.date} 剩:${String.format(Locale.US, "%.2f", lot.remainingShares)}")
                                }
                                if (selectedLotChecks[lot.buyId] == true) {
                                    OutlinedTextField(
                                        value = selectedLotShares[lot.buyId] ?: "",
                                        onValueChange = { selectedLotShares[lot.buyId] = it },
                                        label = { Text("批次${lot.buyId}卖出份额") },
                                        singleLine = true,
                                        modifier = Modifier.fillMaxWidth(),
                                    )
                                }
                                HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
                            }
                        }
                    }
                    if (sellEntryMode == "price") {
                        OutlinedTextField(sellPrice, { sellPrice = it }, label = { Text("卖出确认净值") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    } else {
                        OutlinedTextField(sellAmount, { sellAmount = it }, label = { Text("卖出金额") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    }
                    OutlinedTextField(sellFee, { sellFee = it }, label = { Text("手续费（可选）") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                    val sharesForRisk =
                        if (sellMode == "fifo") (sellShares.toDoubleOrNull() ?: 0.0)
                        else selectedLotShares.filter { selectedLotChecks[it.key] == true }.values.sumOf { it.toDoubleOrNull() ?: 0.0 }
                    val risk = when {
                        remaining <= 1e-9 || sharesForRisk <= 1e-9 -> "none"
                        sharesForRisk + 1e-9 >= remaining -> "clearout"
                        sharesForRisk + 1e-9 >= remaining * 0.5 -> "large"
                        else -> "none"
                    }
                    if (risk != "none") {
                        Text(if (risk == "clearout") "清仓卖出：请勾选确认后再提交。" else "大额卖出（≥50%持仓）：请勾选确认。", color = MaterialTheme.colorScheme.error)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = sellRiskConfirmed, onCheckedChange = { sellRiskConfirmed = it })
                            Text("我已核对份额与价格，确认提交本次卖出")
                        }
                    }
                    Button(
                        onClick = {
                            if (risk != "none" && !sellRiskConfirmed) {
                                onUserMessage("请先勾选确认后再提交卖出。")
                                return@Button
                            }
                            val fee = sellFee.toDoubleOrNull() ?: 0.0
                            scope.launch {
                                if (sellMode == "fifo") {
                                    val sh = sellShares.toDoubleOrNull() ?: 0.0
                                    val price =
                                        if (sellEntryMode == "price") (sellPrice.toDoubleOrNull() ?: 0.0)
                                        else (sellAmount.toDoubleOrNull() ?: 0.0) / maxOf(1e-9, sh)
                                    if (sellConfirmDate.isBlank() || sh <= 0.0 || price <= 0.0) {
                                        onUserMessage("请输入有效的卖出确认日、份额和净值。")
                                        return@launch
                                    }
                                    val r =
                                        tradesRpc(
                                            "add_sell_fifo",
                                            jsonArgs(
                                                mapOf(
                                                    "fund_id" to selectedFundId,
                                                    "confirm_date" to sellConfirmDate,
                                                    "price" to price,
                                                    "shares" to sh,
                                                    "fee" to fee,
                                                ),
                                            ),
                                        )
                                    onUserMessage(if (r.ok) r.message else r.error)
                                    if (r.ok) {
                                        sellRiskConfirmed = false
                                        reload()
                                    }
                                } else {
                                    val picks =
                                        selectedLotShares
                                            .filter { selectedLotChecks[it.key] == true }
                                            .map {
                                                mapOf(
                                                    "buy_tx_id" to it.key,
                                                    "shares" to (it.value.toDoubleOrNull() ?: 0.0),
                                                )
                                            }
                                    val totalSh = picks.sumOf { (it["shares"] as Double) }
                                    val price =
                                        if (sellEntryMode == "price") (sellPrice.toDoubleOrNull() ?: 0.0)
                                        else (sellAmount.toDoubleOrNull() ?: 0.0) / maxOf(1e-9, totalSh)
                                    if (sellConfirmDate.isBlank() || totalSh <= 0.0 || price <= 0.0) {
                                        onUserMessage("请选择有效批次，并输入有效净值/金额。")
                                        return@launch
                                    }
                                    val r =
                                        tradesRpc(
                                            "add_sell_by_lots",
                                            jsonArgs(
                                                mapOf(
                                                    "fund_id" to selectedFundId,
                                                    "confirm_date" to sellConfirmDate,
                                                    "price" to price,
                                                    "picks" to picks,
                                                    "fee" to fee,
                                                ),
                                            ),
                                        )
                                    onUserMessage(if (r.ok) r.message else r.error)
                                    if (r.ok) {
                                        sellRiskConfirmed = false
                                        selectedLotChecks.clear()
                                        selectedLotShares.clear()
                                        reload()
                                    }
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary),
                    ) { Text("记录卖出") }
                }
            }
        }

        if (showAdvanced) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("筛选与交易表", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(txStart, { txStart = it }, label = { Text("开始日期") }, singleLine = true, modifier = Modifier.weight(1f))
                            OutlinedTextField(txEnd, { txEnd = it }, label = { Text("结束日期") }, singleLine = true, modifier = Modifier.weight(1f))
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            FilterChip(selected = txType == "all", onClick = { txType = "all" }, label = { Text("全部") })
                            FilterChip(selected = txType == "buy", onClick = { txType = "buy" }, label = { Text("仅买入") })
                            FilterChip(selected = txType == "sell", onClick = { txType = "sell" }, label = { Text("仅卖出") })
                            TextButton(onClick = { reload() }) { Text("应用筛选") }
                        }
                        p?.warning?.takeIf { it.isNotBlank() }?.let {
                            Text(it, color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }

            if (!p?.transactions.isNullOrEmpty()) {
                items(p!!.transactions) { t ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(10.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                            Column(Modifier.weight(1f)) {
                                Text("${if (t.txType == "buy") "买入" else "卖出"} · ${t.confirmDate}", fontWeight = FontWeight.Medium)
                                Text("价 ${fmt4(t.price)} 份额 ${fmt4(t.shares)} 金额 ${fmtMoney(t.amount)} 手续费 ${fmtMoney(t.fee)}")
                            }
                        }
                    }
                }
            } else {
                item { Text("当前筛选条件下暂无交易记录。") }
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("批量导入（JSON / CSV）", fontWeight = FontWeight.SemiBold)
                        OutlinedTextField(importJsonText, { importJsonText = it }, label = { Text("粘贴 JSON") }, modifier = Modifier.fillMaxWidth().height(120.dp))
                        Button(
                            onClick = {
                                scope.launch {
                                    val r = tradesRpc("import_json", jsonArgs(mapOf("json_text" to importJsonText)))
                                    onUserMessage(if (r.ok) r.message else r.error)
                                    if (r.ok) reload()
                                }
                            },
                        ) { Text("执行 JSON 导入") }
                        OutlinedTextField(importCsvText, { importCsvText = it }, label = { Text("粘贴 CSV") }, modifier = Modifier.fillMaxWidth().height(120.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    val code = p?.selectedFund?.code ?: ""
                                    scope.launch {
                                        val r = tradesRpc("import_csv", jsonArgs(mapOf("csv_text" to importCsvText, "fund_code" to code)))
                                        onUserMessage(if (r.ok) r.message else r.error)
                                        if (r.ok) reload()
                                    }
                                },
                            ) { Text("执行 CSV 导入") }
                            Button(
                                onClick = {
                                    scope.launch {
                                        val r = tradesRpc("export_csv", jsonArgs(mapOf("fund_id" to selectedFundId)))
                                        if (r.ok) {
                                            exportedCsv = r.dataJson?.optString("csv_text", "") ?: ""
                                            onUserMessage("导出成功，已显示在下方文本框。")
                                        } else {
                                            onUserMessage(r.error)
                                        }
                                    }
                                },
                            ) { Text("导出 CSV") }
                        }
                        if (exportedCsv.isNotBlank()) {
                            OutlinedTextField(exportedCsv, { exportedCsv = it }, label = { Text("CSV 导出结果") }, modifier = Modifier.fillMaxWidth().height(120.dp))
                        }
                    }
                }
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("净值曲线", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            listOf("近3月", "近6月", "近1年", "近3年", "近5年", "全部").forEach { r ->
                                FilterChip(
                                    selected = chartRange == r,
                                    onClick = {
                                        chartRange = r
                                        reload()
                                    },
                                    label = { Text(r) },
                                )
                            }
                        }
                        p?.let {
                            TradesNavChartCanvas(navPoints = it.navPoints, buyPoints = it.buyPoints, sellPoints = it.sellPoints)
                            if (it.calendarGaps.isNotEmpty()) {
                                Text("当前范围内有 ${it.calendarGaps.size} 处相邻记录间隔超过14天。", color = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
            }
        }
    }
}
