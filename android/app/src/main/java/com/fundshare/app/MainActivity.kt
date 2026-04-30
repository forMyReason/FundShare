package com.fundshare.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import com.chaquo.python.Python
import com.fundshare.app.ui.FullPayload
import com.fundshare.app.ui.FundShareStreamlitScreen
import com.fundshare.app.ui.TradesPayload
import com.fundshare.app.ui.parseRpcResponse
import com.fundshare.app.ui.parseFullPayload
import com.fundshare.app.ui.parseTradesPayload
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private val StreamlitLikeLight =
    lightColorScheme(
        primary = Color(0xFFFF4B4B),
        onPrimary = Color.White,
        primaryContainer = Color(0xFFFFE8E8),
        secondary = Color(0xFF1F77B4),
        surface = Color(0xFFFFFBFE),
        background = Color(0xFFF8F9FA),
    )

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = StreamlitLikeLight) {
                var payload by remember { mutableStateOf<FullPayload?>(null) }
                var loading by remember { mutableStateOf(true) }
                val snackbarHostState = remember { SnackbarHostState() }

                val scope = rememberCoroutineScope()

                val maintenanceRpc: suspend (String, String) -> String = { op, argJson ->
                    withContext(Dispatchers.Default) {
                        if (!Python.isStarted()) {
                            """{"ok":false,"error":"Python 未启动"}"""
                        } else {
                            val mod = Python.getInstance().getModule("fundshare_android.bridge")
                            mod.callAttr("maintenance_rpc", op, argJson).toString()
                        }
                    }
                }

                val tradesPayloadFetcher: suspend (String) -> TradesPayload = { argJson ->
                    withContext(Dispatchers.Default) {
                        if (!Python.isStarted()) {
                            parseTradesPayload("""{"funds":[],"error":"Python 未启动"}""")
                        } else {
                            val mod = Python.getInstance().getModule("fundshare_android.bridge")
                            val raw = mod.callAttr("trades_payload_json_safe", argJson).toString()
                            parseTradesPayload(raw)
                        }
                    }
                }

                val tradesRpc: suspend (String, String) -> com.fundshare.app.ui.RpcResponse = { op, argJson ->
                    withContext(Dispatchers.Default) {
                        if (!Python.isStarted()) {
                            parseRpcResponse("""{"ok":false,"error":"Python 未启动"}""")
                        } else {
                            val mod = Python.getInstance().getModule("fundshare_android.bridge")
                            val raw = mod.callAttr("trades_rpc", op, argJson).toString()
                            parseRpcResponse(raw)
                        }
                    }
                }

                fun load() {
                    scope.launch {
                        loading = true
                        payload =
                            withContext(Dispatchers.Default) {
                                runCatching { fetchPayloadFromPython() }
                                    .getOrElse { e ->
                                        FullPayload(
                                            version = "",
                                            dataDir = "",
                                            overview = null,
                                            positions = emptyList(),
                                            funds = emptyList(),
                                            transactions = emptyList(),
                                            error = e.message ?: e.toString(),
                                        )
                                    }
                            }
                        loading = false
                    }
                }

                LaunchedEffect(Unit) { load() }

                FundShareStreamlitScreen(
                    payload = payload,
                    loading = loading,
                    onRefresh = { load() },
                    snackbarHostState = snackbarHostState,
                    maintenanceRpc = maintenanceRpc,
                    tradesPayloadFetcher = tradesPayloadFetcher,
                    tradesRpc = tradesRpc,
                )
            }
        }
    }

    private fun fetchPayloadFromPython(): FullPayload {
        if (!Python.isStarted()) {
            return FullPayload(
                version = "",
                dataDir = "",
                overview = null,
                positions = emptyList(),
                funds = emptyList(),
                transactions = emptyList(),
                error = "Python 未启动（检查 PyApplication）",
            )
        }
        val py = Python.getInstance()
        val mod = py.getModule("fundshare_android.bridge")
        val json = mod.callAttr("get_full_ui_payload_json_safe").toString()
        return parseFullPayload(json)
    }
}
