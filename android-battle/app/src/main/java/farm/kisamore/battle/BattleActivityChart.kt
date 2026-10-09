package farm.kisamore.battle

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.view.View
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.math.max

/**
 * A single time axis for watering, feeding and shade periods.
 * Each date label is centered between its two daily grid boundaries.
 * Every mark is derived from a real battle action; no sample chart data.
 */
internal class BattleActivityChart(
    context: Context,
    private val actions: List<BattleAction>,
    private val dark: Boolean,
    private var days: Int = 3
) : View(context) {
    private val d = resources.displayMetrics.density
    private val zone = ZoneId.systemDefault()
    private val labelColor = Color.parseColor(if (dark) "#AEBCAE" else "#738074")
    private val textColor = Color.parseColor(if (dark) "#E9F1E9" else "#26392E")
    private val gridColor = Color.parseColor(if (dark) "#36503F" else "#E1E9E1")
    private val marks = mapOf(
        "water" to Color.parseColor("#65A8D3"),
        "nutrient" to Color.parseColor("#77B590"),
        "shade" to Color.parseColor("#D2AB74")
    )
    private val p = Paint(Paint.ANTI_ALIAS_FLAG)
    fun selectPeriod(value: Int) {
        days = value.coerceIn(1, 7)
        invalidate()
    }

    private fun instant(raw: String?): Instant? {
        if (raw.isNullOrBlank()) return null
        return runCatching { OffsetDateTime.parse(raw).toInstant() }.getOrNull()
            ?: runCatching { Instant.parse(raw) }.getOrNull()
            ?: runCatching { LocalDateTime.parse(raw).atZone(zone).toInstant() }.getOrNull()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0 || h <= 0) return
        val left = 102f * d
        val right = w - 9f * d
        val top = 20f * d
        val bottom = h - 21f * d
        if (right <= left || bottom <= top) return
        val rowGap = (bottom - top) / 3f
        val end: Instant
        val start: Instant
        if (days == 1) {
            end = Instant.now()
            start = end.minus(24, ChronoUnit.HOURS)
        } else {
            val today = LocalDate.now(zone)
            start = today.minusDays((days - 1).toLong()).atStartOfDay(zone).toInstant()
            end = today.plusDays(1).atStartOfDay(zone).toInstant()
        }
        val durationMs = (end.toEpochMilli() - start.toEpochMilli()).toDouble().coerceAtLeast(1.0)
        fun xpos(time: Instant): Float = left +
            (((time.toEpochMilli() - start.toEpochMilli()) / durationMs).coerceIn(0.0, 1.0) * (right - left)).toFloat()
        fun color(c: Int) { p.color = c; p.style = Paint.Style.FILL }
        fun label(text: String, x: Float, y: Float, size: Float, colorValue: Int, center: Boolean = false) {
            color(colorValue); p.typeface = android.graphics.Typeface.DEFAULT
            p.textSize = size * d
            p.textAlign = if (center) Paint.Align.CENTER else Paint.Align.LEFT
            canvas.drawText(text, x, y, p)
        }
        val names = listOf("Полив", "Питание", "Без света")
        names.forEachIndexed { index, title ->
            val y = top + rowGap * (index + .5f)
            label(title, 11f * d, y + 4f * d, 11f, textColor)
            color(gridColor); canvas.drawRect(left, y, right, y + 1f * d, p)
        }
        val columns = if (days == 1) 4 else days
        for (i in 0..columns) {
            val x = left + (right - left) * i / columns
            color(gridColor); canvas.drawRect(x, top, x + .7f * d, bottom, p)
        }
        // The label belongs to the interval, not its boundary.
        for (i in 0 until columns) {
            val centerX = left + (right - left) * (i + .5f) / columns
            val caption = if (days == 1) {
                start.plus((24 * 60 / columns * i + 24 * 60 / columns / 2).toLong(), ChronoUnit.MINUTES)
                    .atZone(zone).format(DateTimeFormatter.ofPattern("HH:mm"))
            } else {
                LocalDate.now(zone).minusDays((days - i - 1).toLong())
                    .format(DateTimeFormatter.ofPattern("dd.MM"))
            }
            label(caption, centerX, h - 5f * d, 9f, labelColor, center = true)
        }
        val filtered = actions.filter { it.status == "completed" || it.status == "done" }
        for (action in filtered) {
            val at = instant(action.completedAt) ?: instant(action.requestedAt) ?: continue
            val row = when (action.kind) { "water" -> 0; "nutrient" -> 1; "shade" -> 2; else -> continue }
            if (at >= end || at < start) {
                if (action.kind != "shade") continue
            }
            val y = top + rowGap * (row + .5f)
            color(marks[action.kind] ?: textColor)
            if (action.kind == "shade") {
                val until = at.plus(action.amount.toLong().coerceAtLeast(1L), ChronoUnit.MINUTES)
                if (until <= start || at >= end) continue
                val fromX = xpos(if (at < start) start else at)
                val toX = xpos(if (until > end) end else until)
                canvas.drawRoundRect(fromX, y - 5f*d, max(fromX + 3f*d, toX), y + 5f*d, 4f*d, 4f*d, p)
            } else if (at >= start && at < end) {
                val x = xpos(at)
                if (action.kind == "water") canvas.drawCircle(x, y, 4f * d, p)
                else canvas.drawRoundRect(x-4f*d, y-4f*d, x+4f*d, y+4f*d, 2f*d, 2f*d, p)
            }
        }
        if (filtered.none { val at = instant(it.completedAt) ?: instant(it.requestedAt); at != null && at >= start && at < end }) {
            label("Нет событий за этот период", (left+right)/2f, top + rowGap*1.5f+4f*d, 10f, labelColor, true)
        }
    }
}
