package com.fundshare.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.util.Locale

private fun mapToArgJson(args: Map<String, Any>): String {
    val o = JSONObject()
    args.forEach { (k, v) ->
        when (v) {
            is Int -> o.put(k, v)
            is Long -> o.put(k, v)
            is Double -> o.put(k, v)
            is String -> o.put(k, v)
            is Boolean -> o.put(k, v)
            else -> o.put(k, v.toString())
        }
    }
    return o.toString()
}

data class MaintenanceRpcResult(
    val ok: Boolean,
    val message: String,
    val error: String,
)

fun parseMaintenanceRpcResult(json: String): MaintenanceRpcResult {
    val o = JSONObject(json)
    return MaintenanceRpcResult(
        ok = o.optBoolean("ok", false),
        message = o.optString("message", ""),
        error = o.optString("error", ""),
    )
}

@Composable
fun MaintenanceTabContent(
    payload: FullPayload,
    maintenanceRpc: suspend (String, String) -> String,
    onAfterSuccess: () -> Unit,
    onUserMessage: (String, Boolean) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var newCode by remember { mutableStateOf("") }
    var fundForDelete by remember { mutableStateOf<FundUi?>(null) }
    var fundForClear by remember { mutableStateOf<FundUi?>(null) }
    var clearConfirmed by remember { mutableStateOf(false) }
    var fundForPurge by remember { mutableStateOf<FundUi?>(null) }
    var purgePhrase by remember { mutableStateOf("") }
    var fundForTx by remember { mutableStateOf<FundUi?>(null) }
    var txToDelete by remember { mutableStateOf<TransactionUi?>(null) }
    var txDeleteConfirmed by remember { mutableStateOf(false) }

    var delMenu by remember { mutableStateOf(false) }
    var clrMenu by remember { mutableStateOf(false) }
    var purMenu by remember { mutableStateOf(false) }
    var txFundMenu by remember { mutableStateOf(false) }
    var txRowMenu by remember { mutableStateOf(false) }

    val funds = payload.funds
    val txsForSelectedFund =
        remember(fundForTx, payload.transactions) {
            if (fundForTx == null) {
                emptyList()
            } else {
                payload.transactions.filter { it.fundId == fundForTx!!.id }
            }
        }

    fun run(
        op: String,
        args: Map<String, Any>,
        onDone: () -> Unit = {},
    ) {
        scope.launch {
            val argJson = mapToArgJson(args)
            val raw = maintenanceRpc(op, argJson)
            val r = parseMaintenanceRpcResult(raw)
            if (r.ok) {
                onUserMessage(r.message.ifBlank { "完成" }, true)
                onAfterSuccess()
                onDone()
            } else {
                onUserMessage(r.error.ifBlank { "操作失败" }, false)
            }
        }
    }

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        item {
            Text("基金维护", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            Text(
                "仅用于：添加基金、删除基金、删除单条交易、一键清空单基金全部记录。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            OutlinedTextField(
                value = newCode,
                onValueChange = { newCode = it },
                label = { Text("基金代码") },
                placeholder = { Text("如 161725") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
            )
            Button(
                onClick = {
                    run("add_fund", mapOf("code" to newCode.trim())) {
                        newCode = ""
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) {
                Text("按代码自动新增基金")
            }
        }

        item {
            Text("基金列表", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        }

        if (funds.isEmpty()) {
            item {
                Text("暂无基金数据。", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            item {
                Card(
                    Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f)),
                ) {
                    Column(Modifier.padding(8.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("序号", fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.15f))
                            Text("代码", fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.22f))
                            Text("名称", fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.38f))
                            Text("净值", fontWeight = FontWeight.Bold, modifier = Modifier.weight(0.25f))
                        }
                        HorizontalDivider(Modifier.padding(vertical = 4.dp))
                        funds.forEachIndexed { idx, f ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text("${idx + 1}", modifier = Modifier.weight(0.15f))
                                Text(f.code, modifier = Modifier.weight(0.22f))
                                Text(f.name, maxLines = 2, modifier = Modifier.weight(0.38f))
                                Text(String.format(Locale.US, "%.6f", f.currentNav), modifier = Modifier.weight(0.25f))
                            }
                        }
                    }
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("删除基金（无持仓时）", fontWeight = FontWeight.SemiBold)
                    Box {
                        TextButton(onClick = { delMenu = true }) {
                            Text(fundForDelete?.let { "${it.code} ${it.name}" } ?: "选择要删除的基金")
                        }
                        DropdownMenu(expanded = delMenu, onDismissRequest = { delMenu = false }) {
                            funds.forEach { f ->
                                DropdownMenuItem(
                                    text = { Text("[${f.code}] ${f.name}") },
                                    onClick = {
                                        fundForDelete = f
                                        delMenu = false
                                    },
                                )
                            }
                        }
                    }
                    Button(
                        onClick = {
                            val f = fundForDelete ?: return@Button
                            run("delete_fund", mapOf("fund_id" to f.id))
                        },
                        enabled = fundForDelete != null,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("确认删除该基金及其历史净值与交易")
                    }
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("一键清空某基金的所有记录（交易+净值）", fontWeight = FontWeight.SemiBold)
                    Box {
                        TextButton(onClick = { clrMenu = true }) {
                            Text(fundForClear?.let { "${it.code} ${it.name}" } ?: "选择要清空记录的基金")
                        }
                        DropdownMenu(expanded = clrMenu, onDismissRequest = { clrMenu = false }) {
                            funds.forEach { f ->
                                DropdownMenuItem(
                                    text = { Text("[${f.code}] ${f.name}") },
                                    onClick = {
                                        fundForClear = f
                                        clrMenu = false
                                    },
                                )
                            }
                        }
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = clearConfirmed, onCheckedChange = { clearConfirmed = it })
                        Text("我确认清空该基金全部交易与净值记录", style = MaterialTheme.typography.bodySmall)
                    }
                    Button(
                        onClick = {
                            val f = fundForClear ?: return@Button
                            if (!clearConfirmed) {
                                onUserMessage("请先勾选确认。", false)
                                return@Button
                            }
                            run("clear_records", mapOf("fund_id" to f.id)) {
                                clearConfirmed = false
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("确认清空该基金记录")
                    }
                }
            }
        }

        item {
            Card(
                Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.25f)),
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("危险操作：一键删除基金及全部记录", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.error)
                    Text(
                        "该操作会删除基金本体、全部交易和全部净值点，不可恢复。",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Box {
                        TextButton(onClick = { purMenu = true }) {
                            Text(fundForPurge?.let { "${it.code} ${it.name}" } ?: "选择要一键删除的基金")
                        }
                        DropdownMenu(expanded = purMenu, onDismissRequest = { purMenu = false }) {
                            funds.forEach { f ->
                                DropdownMenuItem(
                                    text = { Text("[${f.code}] ${f.name}") },
                                    onClick = {
                                        fundForPurge = f
                                        purMenu = false
                                    },
                                )
                            }
                        }
                    }
                    OutlinedTextField(
                        value = purgePhrase,
                        onValueChange = { purgePhrase = it },
                        label = { Text("请输入 DELETE 以确认") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Button(
                        onClick = {
                            val f = fundForPurge ?: return@Button
                            run(
                                "purge_fund",
                                mapOf("fund_id" to f.id, "phrase" to purgePhrase),
                            ) {
                                purgePhrase = ""
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("一键删除基金及全部记录")
                    }
                }
            }
        }

        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("删除买入/卖出记录", fontWeight = FontWeight.SemiBold)
                    Box {
                        TextButton(onClick = { txFundMenu = true }) {
                            Text(fundForTx?.let { "${it.code} ${it.name}" } ?: "选择基金")
                        }
                        DropdownMenu(expanded = txFundMenu, onDismissRequest = { txFundMenu = false }) {
                            funds.forEach { f ->
                                DropdownMenuItem(
                                    text = { Text("[${f.code}] ${f.name}") },
                                    onClick = {
                                        fundForTx = f
                                        txToDelete = null
                                        txFundMenu = false
                                    },
                                )
                            }
                        }
                    }
                    if (txsForSelectedFund.isEmpty() && fundForTx != null) {
                        Text("该基金暂无交易记录。", style = MaterialTheme.typography.bodySmall)
                    }
                    if (txsForSelectedFund.isNotEmpty()) {
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .height(180.dp)
                                .verticalScroll(rememberScrollState()),
                        ) {
                            txsForSelectedFund.sortedByDescending { it.confirmDate }.forEach { tx ->
                                Text(
                                    "#${tx.id} ${tx.txType} ${tx.confirmDate} 份额:${String.format(Locale.US, "%.2f", tx.shares)}",
                                    style = MaterialTheme.typography.bodySmall,
                                    modifier = Modifier.padding(vertical = 2.dp),
                                )
                            }
                        }
                        Box {
                            TextButton(onClick = { txRowMenu = true }) {
                                Text(
                                    txToDelete?.let { "#${it.id} ${it.txType} ${it.confirmDate}" }
                                        ?: "选择要删除的交易",
                                )
                            }
                            DropdownMenu(expanded = txRowMenu, onDismissRequest = { txRowMenu = false }) {
                                txsForSelectedFund.forEach { tx ->
                                    DropdownMenuItem(
                                        text = {
                                            Text("#${tx.id} ${tx.txType} ${tx.confirmDate} ${tx.shares}")
                                        },
                                        onClick = {
                                            txToDelete = tx
                                            txRowMenu = false
                                        },
                                    )
                                }
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = txDeleteConfirmed, onCheckedChange = { txDeleteConfirmed = it })
                            Text("我确认删除该交易记录", style = MaterialTheme.typography.bodySmall)
                        }
                        Button(
                            onClick = {
                                val fund = fundForTx ?: return@Button
                                val tx = txToDelete ?: return@Button
                                if (!txDeleteConfirmed) {
                                    onUserMessage("请先勾选确认。", false)
                                    return@Button
                                }
                                run(
                                    "delete_tx",
                                    mapOf("fund_id" to fund.id, "tx_id" to tx.id),
                                ) {
                                    txDeleteConfirmed = false
                                    txToDelete = null
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("确认删除交易")
                        }
                    }
                }
            }
        }

        item {
            HorizontalDivider()
            Spacer(Modifier.height(4.dp))
            Text("关于", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text("核心版本（fundshare）：${payload.version}", style = MaterialTheme.typography.bodySmall)
            Text(
                "数据目录：${payload.dataDir.ifBlank { "（应用私有目录）" }}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
