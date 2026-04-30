package com.fundshare.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.chaquo.python.Python

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val status = remember { mutableStateOf("加载中…") }
            LaunchedEffect(Unit) {
                status.value = runPythonSummary()
            }
            MaterialTheme {
                FundShareScreen(
                    statusLine = status.value,
                    onRefresh = { status.value = runPythonSummary() },
                )
            }
        }
    }

    private fun runPythonSummary(): String {
        return try {
            if (!Python.isStarted()) {
                return "Python 未启动（检查 PyApplication）"
            }
            val py = Python.getInstance()
            val mod = py.getModule("fundshare_android.bridge")
            mod.callAttr("get_status_line").toString()
        } catch (e: Exception) {
            e.message ?: e.toString()
        }
    }
}

@Composable
fun FundShareScreen(
    statusLine: String,
    onRefresh: () -> Unit,
) {
    Surface(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(text = stringResource(R.string.python_status_label))
            Spacer(modifier = Modifier.height(12.dp))
            Text(text = statusLine)
            Spacer(modifier = Modifier.height(16.dp))
            Button(onClick = onRefresh) {
                Text(stringResource(R.string.python_refresh))
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun PreviewFundShare() {
    FundShareScreen(statusLine = "示例", onRefresh = {})
}
