package com.fundshare.app.ui

import android.app.DatePickerDialog
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.util.Locale

private fun fmtMoney(v: Double): String = String.format(Locale.US, "%.2f", v)

private fun fmt4(v: Double): String = String.format(Locale.US, "%.4f", v)
private val ModeSelectedBg = Color(0xFFE9D5FF)
private val ModeSelectedText = Color(0xFF5B21B6)
private val ModeUnselectedBg = Color(0xFFF3F4F6)
private val ModeUnselectedText = Color(0xFF374151)

private fun isIsoDate(v: String): Boolean = runCatching { LocalDate.parse(v); true }.getOrDefault(false)

private fun showDatePicker(
    currentValue: String,
    onPick: (String) -> Unit,
    createDialog: (year: Int, month: Int, day: Int, onDateSet: (Int, Int, Int) -> Unit) -> DatePickerDialog,
) {
    val current = runCatching { LocalDate.parse(currentValue) }.getOrDefault(LocalDate.now())
    createDialog(current.year, current.monthValue - 1, current.dayOfMonth)
    { year, month, day ->
        onPick(LocalDate.of(year, month + 1, day).toString())
    }.show()
}

@Composable
private fun DateFieldWithPicker(
    label: String,
    value: String,
    onPick: (String) -> Unit,
    context: android.content.Context,
    modifier: Modifier = Modifier,
) {
    val openPicker = {
        showDatePicker(
            currentValue = value,
            onPick = onPick,
            createDialog = { y, m, d, onDateSet ->
                DatePickerDialog(context, { _, yy, mm, dd -> onDateSet(yy, mm, dd) }, y, m, d)
            },
        )
    }
    Box(
        modifier =
            modifier.pointerInput(value) {
                detectTapGestures(onTap = { openPicker() })
            },
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            label = { Text(label) },
            readOnly = true,
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun ModeToggleButton(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        colors =
            if (selected) {
                ButtonDefaults.buttonColors(containerColor = ModeSelectedBg, contentColor = ModeSelectedText)
            } else {
                ButtonDefaults.buttonColors(containerColor = ModeUnselectedBg, contentColor = ModeUnselectedText)
            },
    ) { Text(text) }
}

@Composable
private fun SoftActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        colors = ButtonDefaults.buttonColors(containerColor = ModeSelectedBg, contentColor = ModeSelectedText),
    ) { Text(text) }
}

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
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val funds = fullPayload.funds
    var selectedFundId by remember { mutableStateOf(funds.firstOrNull()?.id ?: 0) }
    var txStart by remember { mutableStateOf(LocalDate.now().withDayOfMonth(1).toString()) }
    var txEnd by remember { mutableStateOf(LocalDate.now().toString()) }
    var txType by remember { mutableStateOf("all") }
    var chartRange by remember { mutableStateOf("近1年") }
    var showRelativeNav by remember { mutableStateOf(false) }
    var showSellPointsInChart by remember { mutableStateOf(true) }
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
                            ModeToggleButton(
                                text = "${f.code} ${f.name.take(4)}",
                                selected = selectedFundId == f.id,
                                onClick = { selectedFundId = f.id },
                            )
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SoftActionButton(text = "刷新", onClick = { reload() }, modifier = Modifier.fillMaxWidth())
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
                    DateFieldWithPicker(
                        label = "买入确认日（YYYY-MM-DD）",
                        value = buyConfirmDate,
                        onPick = { buyConfirmDate = it },
                        context = context,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ModeToggleButton("按净值+份额", buyMode == "price", { buyMode = "price" }, Modifier.weight(1f))
                        ModeToggleButton("按金额+份额", buyMode == "amount", { buyMode = "amount" }, Modifier.weight(1f))
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
                    SoftActionButton(
                        text = "记录买入",
                        onClick = {
                            val sh = buyShares.toDoubleOrNull() ?: 0.0
                            val fee = buyFee.toDoubleOrNull() ?: 0.0
                            val price =
                                if (buyMode == "price") (buyPrice.toDoubleOrNull() ?: 0.0)
                                else (buyAmount.toDoubleOrNull() ?: 0.0) / maxOf(1e-9, sh)
                            if (!isIsoDate(buyConfirmDate) || sh <= 0.0 || price <= 0.0) {
                                onUserMessage("请输入有效的买入确认日、份额和净值。")
                                return@SoftActionButton
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
                    )
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("卖出", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text("当前可卖出份额：${String.format(Locale.US, "%.2f", remaining)}", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    DateFieldWithPicker(
                        label = "卖出确认日（YYYY-MM-DD）",
                        value = sellConfirmDate,
                        onPick = { sellConfirmDate = it },
                        context = context,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ModeToggleButton("FIFO 自动", sellMode == "fifo", { sellMode = "fifo" }, Modifier.weight(1f))
                        ModeToggleButton("指定批次", sellMode == "lots", { sellMode = "lots" }, Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ModeToggleButton("按净值+份额", sellEntryMode == "price", { sellEntryMode = "price" }, Modifier.weight(1f))
                        ModeToggleButton("按金额+份额", sellEntryMode == "amount", { sellEntryMode = "amount" }, Modifier.weight(1f))
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
                    SoftActionButton(
                        text = "记录卖出",
                        onClick = {
                            if (risk != "none" && !sellRiskConfirmed) {
                                onUserMessage("请先勾选确认后再提交卖出。")
                                return@SoftActionButton
                            }
                            val fee = sellFee.toDoubleOrNull() ?: 0.0
                            scope.launch {
                                if (sellMode == "fifo") {
                                    val sh = sellShares.toDoubleOrNull() ?: 0.0
                                    val price =
                                        if (sellEntryMode == "price") (sellPrice.toDoubleOrNull() ?: 0.0)
                                        else (sellAmount.toDoubleOrNull() ?: 0.0) / maxOf(1e-9, sh)
                                    if (!isIsoDate(sellConfirmDate) || sh <= 0.0 || price <= 0.0) {
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
                                    if (!isIsoDate(sellConfirmDate) || totalSh <= 0.0 || price <= 0.0) {
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
                    )
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("净值曲线", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(
                        "净值曲线说明与数据区间",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("近3月", "近6月", "近1年", "近3年", "近5年", "全部").forEach { option ->
                            ModeToggleButton(
                                text = option,
                                selected = chartRange == option,
                                onClick = {
                                    chartRange = option
                                    reload()
                                },
                            )
                        }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = showRelativeNav, onCheckedChange = { showRelativeNav = it })
                        Text("显示相对净值点涨跌(右轴, %)")
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = showSellPointsInChart, onCheckedChange = { showSellPointsInChart = it })
                        Text("显示卖出点")
                    }
                    p?.let {
                        TradesNavChartCanvas(
                            navPoints = it.navPoints,
                            buyPoints = it.buyPoints,
                            sellPoints = it.sellPoints,
                            showRelative = showRelativeNav,
                            showSellPoints = showSellPointsInChart,
                        )
                        if (it.navPoints.isEmpty()) {
                            Text("当前区间内暂无入点。", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (it.calendarGaps.isNotEmpty()) {
                            Text("当前范围内有 ${it.calendarGaps.size} 处相邻记录间隔超过14天。", color = MaterialTheme.colorScheme.error)
                        }
                    } ?: Text("正在加载曲线数据…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("筛选与交易表", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            DateFieldWithPicker(
                                label = "开始日期",
                                value = txStart,
                                onPick = { txStart = it },
                                context = context,
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            DateFieldWithPicker(
                                label = "结束日期",
                                value = txEnd,
                                onPick = { txEnd = it },
                                context = context,
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        ModeToggleButton("全部", txType == "all", { txType = "all" })
                        ModeToggleButton("仅买入", txType == "buy", { txType = "buy" })
                        ModeToggleButton("仅卖出", txType == "sell", { txType = "sell" })
                        SoftActionButton(text = "应用筛选", onClick = { reload() })
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
    }
}
