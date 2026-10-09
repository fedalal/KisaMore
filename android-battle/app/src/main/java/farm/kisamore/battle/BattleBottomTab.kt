package farm.kisamore.battle

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

/** Minimal four-tab navigation matching the KisaMore Battle profile design. */
class BattleBottomTab(
    context: Context,
    title: String,
    icon: String,
    selected: Boolean,
    onTap: () -> Unit
) : LinearLayout(context) {
    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER
        val tint = Color.parseColor(if (selected) "#24683C" else "#7B827A")
        addView(BattleTabGlyph(context, icon, tint), LayoutParams(px(26), px(27)))
        addView(TextView(context).apply {
            text = title
            textSize = 10f
            setTextColor(tint)
            gravity = Gravity.CENTER
            maxLines = 1
        }, LayoutParams(-1, px(19)))
        isClickable = true
        isFocusable = true
        contentDescription = title
        setOnClickListener { onTap() }
    }
    private fun px(n: Int) = (n * resources.displayMetrics.density).toInt()
}

/** Vector icons drawn in code: no emoji, fonts or drawable dependencies. */
private class BattleTabGlyph(context: Context, private val glyph: String, private val tint: Int) : View(context) {
    private val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = tint
        strokeWidth = 2.1f
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
        style = Paint.Style.STROKE
    }
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.save()
        canvas.scale(width / 24f, height / 24f)
        when (glyph) {
            "plant" -> {
                val leaf = Path().apply {
                    moveTo(4f, 17f); cubicTo(4f, 8f, 13f, 4f, 21f, 3f)
                    cubicTo(21f, 13f, 16f, 20f, 7f, 20f)
                    cubicTo(6f, 20f, 4f, 19f, 4f, 17f)
                }
                canvas.drawPath(leaf, p)
                canvas.drawLine(5f, 22f, 17f, 9f, p)
            }
            "battle" -> {
                canvas.drawLine(5f, 3f, 19f, 19f, p)
                canvas.drawLine(19f, 3f, 5f, 19f, p)
                canvas.drawLine(3f, 17f, 8f, 22f, p)
                canvas.drawLine(21f, 17f, 16f, 22f, p)
                canvas.drawLine(5f, 21f, 9f, 17f, p)
                canvas.drawLine(19f, 21f, 15f, 17f, p)
            }
            "history" -> {
                canvas.drawCircle(12f, 12f, 9f, p)
                canvas.drawLine(12f, 6f, 12f, 12f, p)
                canvas.drawLine(12f, 12f, 16f, 15f, p)
            }
            else -> {
                p.style = Paint.Style.FILL
                canvas.drawCircle(12f, 7f, 4f, p)
                canvas.drawRoundRect(5f, 13f, 19f, 22f, 6f, 6f, p)
                p.style = Paint.Style.STROKE
            }
        }
        canvas.restore()
    }
}
