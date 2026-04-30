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
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor

private data class ChartPt(val x: Float, val y: Float, val date: String, val nav: Double)
private data class RelativePt(val x: Float, val y: Float, val date: String, val ratio: Double)

private fun smoothLine(points: List<Offset>): Path {
    val path = Path()
    if (points.isEmpty()) return path
    path.moveTo(points.first().x, points.first().y)
    if (points.size == 1) return path
    for (i in 1 until points.size) {
        val prev = points[i - 1]
        val curr = points[i]
        val c1 = Offset((prev.x + curr.x) * 0.5f, prev.y)
        val c2 = Offset((prev.x + curr.x) * 0.5f, curr.y)
        path.cubicTo(c1.x, c1.y, c2.x, c2.y, curr.x, curr.y)
    }
    return path
}

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
    val colorScheme = MaterialTheme.colorScheme
    val chartBgColor = colorScheme.surface
    val gridColor = colorScheme.outline.copy(alpha = 0.22f)
    val axisColor = colorScheme.outline.copy(alpha = 0.65f)
    val axisTextColor = android.graphics.Color.parseColor("#6B7280")

    Column(modifier = modifier) {
        Canvas(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(260.dp)
                    .background(chartBgColor)
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
            val yStep = maxOf(0.0001, minNav * 0.04)
            val yStart = floor(minNav / yStep) * yStep
            val yEnd = ceil(maxNav / yStep) * yStep
            val yTicks = mutableListOf<Double>()
            var curr = yStart
            while (curr <= yEnd + 1e-9) {
                yTicks.add(curr)
                curr += yStep
            }

            drawLine(color = axisColor, start = Offset(0f, 0f), end = Offset(0f, size.height), strokeWidth = 2f)
            drawLine(color = axisColor, start = Offset(0f, size.height), end = Offset(size.width, size.height), strokeWidth = 2f)

            val labelPaint =
                android.graphics.Paint().apply {
                    color = axisTextColor
                    textSize = 24f
                    isAntiAlias = true
                }

            yTicks.forEach { tick ->
                val norm = ((tick - minNav) / navSpan).toFloat().coerceIn(0f, 1f)
                val y = size.height * (1f - norm)
                drawLine(
                    color = gridColor,
                    start = Offset(0f, y),
                    end = Offset(size.width, y),
                    strokeWidth = 1f,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f)),
                )
                drawContext.canvas.nativeCanvas.drawText("%.4f".format(tick), 6f, y - 6f, labelPaint)
            }

            val pts =
                parsed.map { (d, v) ->
                    val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                    val x = size.width * dx
                    val dy = ((v - minNav) / navSpan).toFloat()
                    val y = size.height * (1f - dy)
                    ChartPt(x, y, d.toString(), v)
                }
            val navLine = smoothLine(pts.map { Offset(it.x, it.y) })
            drawPath(
                path = navLine,
                color = Color(0xFFF59E0B),
                style = Stroke(width = 4f, cap = StrokeCap.Round),
            )

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
                val relativeLine = smoothLine(relativePts.map { Offset(it.x, it.y) })
                drawPath(
                    path = relativeLine,
                    color = Color(0xFF9CA3AF),
                    style = Stroke(width = 2.5f, cap = StrokeCap.Round),
                )
            }

            buyPoints.forEach { b ->
                val d = runCatching { LocalDate.parse(b.date) }.getOrNull() ?: return@forEach
                val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                val x = size.width * dx
                val dy = ((b.price - minNav) / navSpan).toFloat()
                val y = size.height * (1f - dy)
                drawCircle(color = Color.White, radius = 6.5f, center = Offset(x, y))
                drawCircle(color = Color(0xFF10B981), radius = 4.5f, center = Offset(x, y))
            }
            if (showSellPoints) {
                sellPoints.forEach { s ->
                    val d = runCatching { LocalDate.parse(s.date) }.getOrNull() ?: return@forEach
                    val dx = ChronoUnit.DAYS.between(minDate, d).toFloat() / spanDays.toFloat()
                    val x = size.width * dx
                    val dy = ((s.price - minNav) / navSpan).toFloat()
                    val y = size.height * (1f - dy)
                    drawCircle(color = Color.White, radius = 6.5f, center = Offset(x, y))
                    drawCircle(color = Color(0xFFEF4444), radius = 4.5f, center = Offset(x, y))
                }
            }
            selected?.let { p ->
                drawLine(
                    color = Color(0xFF666666),
                    start = Offset(p.x, 0f),
                    end = Offset(p.x, size.height),
                    strokeWidth = 1.5f,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 8f)),
                )
                drawCircle(color = Color(0xFFF59E0B), radius = 5f, center = Offset(p.x, p.y))
            }
            val xLabelPaint =
                android.graphics.Paint().apply {
                    color = axisTextColor
                    textSize = 24f
                    isAntiAlias = true
                    textAlign = android.graphics.Paint.Align.CENTER
                }
            val startLabel = minDate.toString()
            val midLabel = minDate.plusDays(spanDays / 2).toString()
            val endLabel = maxDate.toString()
            drawContext.canvas.nativeCanvas.drawText(startLabel, 56f, size.height - 8f, xLabelPaint)
            drawContext.canvas.nativeCanvas.drawText(midLabel, size.width / 2f, size.height - 8f, xLabelPaint)
            drawContext.canvas.nativeCanvas.drawText(endLabel, size.width - 56f, size.height - 8f, xLabelPaint)
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
            Text("橙线: 本基金", style = MaterialTheme.typography.labelSmall, color = Color(0xFFF59E0B))
            if (showRelative) {
                Text("灰线: 相对涨跌(%)", style = MaterialTheme.typography.labelSmall, color = Color(0xFF9CA3AF))
            }
            Text("绿点: 买入点", style = MaterialTheme.typography.labelSmall, color = Color(0xFF2E7D32))
            if (showSellPoints) {
                Text("红点: 卖出点", style = MaterialTheme.typography.labelSmall, color = Color(0xFFC62828))
            }
        }
    }
}
