package com.fundshare.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.abs

private data class ChartPt(val x: Float, val y: Float, val date: String, val nav: Double)
private data class RelativePt(val x: Float, val y: Float, val date: String, val ratio: Double)

@Composable
fun TradesNavChartCanvas(
    navPoints: List<NavPointUi>,
    buyPoints: List<BuyPointUi>,
    sellPoints: List<SellPointUi>,
    showRelative: Boolean,
    showSellPoints: Boolean,
    modifier: Modifier = Modifier,
) {
    if (navPoints.isEmpty()) {
        Text("暂无净值数据，无法绘制曲线。")
        return
    }

    var selected by remember { mutableStateOf<ChartPt?>(null) }
    val parsed =
        navPoints
            .mapNotNull {
                runCatching { LocalDate.parse(it.date) to it.nav }.getOrNull()
            }.sortedBy { it.first }
    if (parsed.isEmpty()) {
        Text("净值日期解析失败。")
        return
    }

    val minDate = parsed.first().first
    val maxDate = parsed.last().first
    val spanDays = maxOf(1L, ChronoUnit.DAYS.between(minDate, maxDate))
    val minNav = parsed.minOf { it.second }
    val maxNav = parsed.maxOf { it.second }
    val navSpan = if (maxNav - minNav < 1e-9) 1.0 else (maxNav - minNav)
    val baseNav = parsed.first().second

    val relativeParsed =
        if (baseNav <= 1e-9) {
            emptyList()
        } else {
            parsed.map { (d, v) -> d to ((v / baseNav - 1.0) * 100.0) }
        }
    val minRelative = relativeParsed.minOfOrNull { it.second } ?: -1.0
    val maxRelative = relativeParsed.maxOfOrNull { it.second } ?: 1.0
    val relativeSpan = if (maxRelative - minRelative < 1e-9) 1.0 else (maxRelative - minRelative)

    Column(modifier = modifier) {
        Canvas(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(260.dp)
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.2f))
                    .padding(8.dp)
                    .pointerInput(parsed) {
                        detectTapGestures { pos ->
                            val pts =
                                parsed.map { (d, v) ->
                                    val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                                    val x = size.width * dx
                                    val dy = ((v - minNav) / navSpan).toFloat()
                                    val y = size.height * (1f - dy)
                                    ChartPt(x, y, d.toString(), v)
                                }
                            selected = pts.minByOrNull { abs(it.x - pos.x) + abs(it.y - pos.y) }
                        }
                    },
        ) {
            val pts =
                parsed.map { (d, v) ->
                    val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                    val x = size.width * dx
                    val dy = ((v - minNav) / navSpan).toFloat()
                    val y = size.height * (1f - dy)
                    ChartPt(x, y, d.toString(), v)
                }
            val path = Path()
            pts.forEachIndexed { idx, p ->
                if (idx == 0) path.moveTo(p.x, p.y) else path.lineTo(p.x, p.y)
            }
            drawPath(path, color = Color(0xFF1F77B4))

            val relativePts =
                if (!showRelative || relativeParsed.isEmpty()) {
                    emptyList()
                } else {
                    relativeParsed.map { (d, ratio) ->
                        val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                        val x = size.width * dx
                        val dy = ((ratio - minRelative) / relativeSpan).toFloat()
                        val y = size.height * (1f - dy)
                        RelativePt(x, y, d.toString(), ratio)
                    }
                }
            if (relativePts.isNotEmpty()) {
                val relativePath = Path()
                relativePts.forEachIndexed { idx, p ->
                    if (idx == 0) relativePath.moveTo(p.x, p.y) else relativePath.lineTo(p.x, p.y)
                }
                drawPath(relativePath, color = Color(0xFFEF6C00))
            }

            buyPoints.forEach { b ->
                val d = runCatching { LocalDate.parse(b.date) }.getOrNull() ?: return@forEach
                val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                val x = size.width * dx
                val dy = ((b.price - minNav) / navSpan).toFloat()
                val y = size.height * (1f - dy)
                drawCircle(color = Color(0xFF2E7D32), radius = 5f, center = Offset(x, y))
            }
            if (showSellPoints) {
                sellPoints.forEach { s ->
                    val d = runCatching { LocalDate.parse(s.date) }.getOrNull() ?: return@forEach
                    val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                    val x = size.width * dx
                    val dy = ((s.price - minNav) / navSpan).toFloat()
                    val y = size.height * (1f - dy)
                    drawCircle(color = Color(0xFFC62828), radius = 5f, center = Offset(x, y))
                }
            }
            selected?.let { p ->
                drawLine(
                    color = Color(0xFF666666),
                    start = Offset(p.x, 0f),
                    end = Offset(p.x, size.height),
                    strokeWidth = 1.5f,
                )
            }
        }
        selected?.let {
            Text(
                "选中：${it.date} 净值 ${"%.4f".format(it.nav)}",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        Row(
            modifier = Modifier.padding(top = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("蓝线: 净值", style = MaterialTheme.typography.labelSmall, color = Color(0xFF1F77B4))
            if (showRelative) {
                Text("橙线: 相对涨跌(%)", style = MaterialTheme.typography.labelSmall, color = Color(0xFFEF6C00))
            }
            Text("绿点: 买入点", style = MaterialTheme.typography.labelSmall, color = Color(0xFF2E7D32))
            if (showSellPoints) {
                Text("红点: 卖出点", style = MaterialTheme.typography.labelSmall, color = Color(0xFFC62828))
            }
        }
    }
}
