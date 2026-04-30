package com.fundshare.app.ui

import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import kotlinx.coroutines.launch
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.util.Locale

private enum class MainTab(
    val label: String,
) {
    PORTFOLIO("组合总览"),
    FUNDS("基金管理"),
    TRADES("交易与净值"),
    MAINT("维护"),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FundShareStreamlitScreen(
    payload: FullPayload?,
    loading: Boolean,
    onRefresh: () -> Unit,
    snackbarHostState: SnackbarHostState,
    maintenanceRpc: suspend (String, String) -> String,
    tradesPayloadFetcher: suspend (String) -> TradesPayload,
    tradesRpc: suspend (String, String) -> RpcResponse,
) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    val tabs = MainTab.entries
    val snackScope = rememberCoroutineScope()

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("个人基金交易记录器", style = MaterialTheme.typography.titleLarge)
                        Text(
                            "买入以确认日为准；与 Streamlit 网页版共用 fundshare 核心",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onRefresh, enabled = !loading) {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { index, t ->
                    NavigationBarItem(
                        selected = tab == index,
                        onClick = { tab = index },
                        icon = { Text(t.label.take(2)) },
                        label = { Text(t.label) },
                    )
                }
            }
        },
    ) { inner ->
        Column(
            Modifier
                .padding(inner)
                .fillMaxSize()
                .padding(horizontal = 16.dp),
        ) {
            when {
                loading -> Text("加载中…", modifier = Modifier.padding(top = 24.dp))
                payload == null -> Text("暂无数据", modifier = Modifier.padding(top = 24.dp))
                !payload.error.isNullOrBlank() -> ErrorBanner(payload.error)
                else -> when (tabs[tab]) {
                    MainTab.PORTFOLIO -> PortfolioTab(payload)
                    MainTab.FUNDS -> FundsTab(payload)
                    MainTab.TRADES ->
                        TradesTabContent(
                            fullPayload = payload,
                            fetchPayload = tradesPayloadFetcher,
                            tradesRpc = tradesRpc,
                            onUserMessage = { msg ->
                                snackScope.launch {
                                    snackbarHostState.showSnackbar(
                                        message = msg,
                                        withDismissAction = true,
                                    )
                                }
                            },
                        )
                    MainTab.MAINT ->
                        MaintenanceTabContent(
                            payload = payload,
                            maintenanceRpc = maintenanceRpc,
                            onAfterSuccess = onRefresh,
                            onUserMessage = { msg, _ ->
                                snackScope.launch {
                                    snackbarHostState.showSnackbar(
                                        message = msg,
                                        withDismissAction = true,
                                    )
                                }
                            },
                        )
                }
            }
        }
    }
}

@Composable
private fun ErrorBanner(message: String) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
        modifier = Modifier.padding(top = 16.dp),
    ) {
        Text(
            message,
            modifier = Modifier.padding(16.dp),
            color = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

@Composable
private fun PortfolioTab(payload: FullPayload) {
    val ov = payload.overview
    LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text("组合概览", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
        }
        if (ov != null) {
            item { MetricsBlock(ov) }
            item {
                Text(
                    "扣费后已实现盈亏：${fmtMoney(ov.realizedPnlAfterFees)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        } else {
            item {
                Text(
                    "暂无组合概览数据（请下拉刷新或查看维护页错误提示）。",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        item {
            Spacer(Modifier.height(8.dp))
            HorizontalDivider()
            Text(
                "多基金持仓对比",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 12.dp, bottom = 8.dp),
            )
        }
        if (payload.positions.isEmpty()) {
            item { Text("暂无持仓基金数据。", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else {
            items(payload.positions, key = { "${it.code}_${it.name}" }) { p ->
                PositionCard(p)
            }
        }
    }
}

@Composable
private fun MetricsBlock(ov: OverviewUi) {
    val pairs =
        listOf(
            "总成本" to ov.totalCost,
            "总市值" to ov.totalValue,
            "浮动盈亏" to ov.totalPnl,
            "组合收益率" to (ov.pnlRatio * 100.0),
            "累计买入" to ov.buyAmount,
            "累计卖出" to ov.sellAmount,
            "已实现盈亏" to ov.realizedPnl,
            "累计手续费" to ov.totalFees,
        )
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        pairs.chunked(2).forEach { row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { (label, value) ->
                    MetricTile(
                        label = label,
                        value =
                            if (label == "组合收益率") {
                                String.format(Locale.US, "%.2f%%", value)
                            } else {
                                fmtMoney(value)
                            },
                        modifier = Modifier.weight(1f),
                    )
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun MetricTile(label: String, value: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium)
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun PositionCard(p: PositionUi) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text("${p.code}  ${p.name}", fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                MiniStat("持仓份额", fmt4(p.holdingShares))
                MiniStat("持仓成本", fmtMoney(p.holdingCost))
                MiniStat("估值", fmtMoney(p.marketValue))
                MiniStat("浮动盈亏", fmtMoney(p.floatingPnl), valueColor(p.floatingPnl))
                MiniStat("当前净值", fmt4(p.currentNav))
                MiniStat("简易年化", String.format(Locale.US, "%.2f%%", p.annualizedSimpleRatio * 100))
            }
        }
    }
}

@Composable
private fun MiniStat(label: String, value: String, valueColor: Color = Color.Unspecified) {
    val resolved =
        if (valueColor == Color.Unspecified) MaterialTheme.colorScheme.onSurface else valueColor
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, color = resolved)
    }
}

private fun valueColor(pnl: Double): Color =
    when {
        pnl > 1e-6 -> Color(0xFF2E7D32)
        pnl < -1e-6 -> Color(0xFFC62828)
        else -> Color.Unspecified
    }

private fun fmtMoney(v: Double): String = String.format(Locale.US, "%.2f", v)

private fun fmt4(v: Double): String = String.format(Locale.US, "%.4f", v)

@Composable
private fun FundsTab(payload: FullPayload) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Text("持有基金", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                "与网页版「基金管理」同源；增删改交易请在网页或后续版本完成。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
        }
        if (payload.funds.isEmpty()) {
            item { Text("暂无基金数据。") }
        } else {
            items(payload.funds, key = { "${it.id}_${it.code}" }) { f ->
                Card(Modifier.fillMaxWidth()) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column {
                            Text(f.code, fontWeight = FontWeight.SemiBold)
                            Text(f.name, style = MaterialTheme.typography.bodySmall)
                        }
                        Text("净值 ${fmt4(f.currentNav)}", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}

@Composable
private fun TradesTab(payload: FullPayload) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Text("交易记录（按确认日倒序）", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                "净值曲线与 Plotly 交互图仍在网页端体验更佳；此处展示最近成交摘要。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
        }
        if (payload.transactions.isEmpty()) {
            item { Text("暂无交易。") }
        } else {
            itemsIndexed(payload.transactions) { _, t ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            "${t.fundCode} · ${t.fundName}",
                            fontWeight = FontWeight.Medium,
                        )
                        val typeLabel = if (t.txType == "buy") "买入" else "卖出"
                        val typeColor = if (t.txType == "buy") Color(0xFF1565C0) else Color(0xFF6A1B9A)
                        Text(
                            "$typeLabel  确认日 ${t.confirmDate}",
                            color = typeColor,
                            style = MaterialTheme.typography.labelLarge,
                        )
                        Text("份额 ${fmt4(t.shares)}  金额 ${fmtMoney(t.amount)}  价 ${fmt4(t.price)}")
                    }
                }
            }
        }
    }
}
