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
        // Square artwork; always 19x19 dp, never scaled to fill a tall tab.
        addView(BattleTabGlyph(context, icon, tint), LayoutParams(px(23), px(23)))
        addView(TextView(context).apply {
            text = title
            textSize = 10f
            includeFontPadding = false
            setTextColor(tint)
            gravity = Gravity.CENTER
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            setPadding(0, px(2), 0, 0)
        }, LayoutParams(-1, px(16)))
        isClickable = true
        isFocusable = true
        contentDescription = title
        setOnClickListener { onTap() }
    }
    private fun px(n: Int) = (n * resources.displayMetrics.density).toInt()
}

/** Vector icons drawn in code: no emoji, fonts or drawable dependencies. */
internal class BattleTabGlyph(context: Context, private val glyph: String, private val tint: Int) : View(context) {
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
        val scale = minOf(width, height) / 24f
        canvas.translate((width - 24f * scale) / 2f, (height - 24f * scale) / 2f)
        canvas.scale(scale, scale)
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
                // Official Lucide "swords" geometry (24x24) as in Figma.
                val left = Path().apply {
                    moveTo(13f, 19f); lineTo(19f, 13f)
                    moveTo(14.5f, 17.5f); lineTo(3.586f, 6.586f)
                    cubicTo(3.211f, 6.211f, 3f, 5.702f, 3f, 5.172f)
                    lineTo(3f, 3f); lineTo(5.172f, 3f)
                    cubicTo(5.702f, 3f, 6.211f, 3.211f, 6.586f, 3.586f)
                    lineTo(17.5f, 14.5f)
                    moveTo(14.828f, 6.172f); lineTo(17.414f, 3.586f)
                    cubicTo(17.789f, 3.211f, 18.298f, 3f, 18.828f, 3f)
                    lineTo(21f, 3f); lineTo(21f, 5.172f)
                    cubicTo(21f, 5.702f, 20.789f, 6.211f, 20.414f, 6.586f)
                    lineTo(17.828f, 9.172f)
                    moveTo(16f, 16f); lineTo(20f, 20f)
                    moveTo(19f, 21f); lineTo(21f, 19f)
                    moveTo(5f, 14f); lineTo(9f, 18f)
                    moveTo(5f, 21f); lineTo(3f, 19f)
                    moveTo(7.5f, 16.5f); lineTo(4f, 20f)
                }
                canvas.drawPath(left, p)
            }
            "trophy" -> {
                canvas.drawRoundRect(7f, 3f, 17f, 15f, 2f, 2f, p)
                canvas.drawArc(3f, 5f, 10f, 14f, 90f, 190f, false, p)
                canvas.drawArc(14f, 5f, 21f, 14f, 260f, 190f, false, p)
                canvas.drawLine(12f, 15f, 12f, 20f, p)
                canvas.drawLine(7f, 21f, 17f, 21f, p)
            }
            "chart" -> {
                canvas.drawRoundRect(3f, 13f, 7f, 21f, 1f, 1f, p)
                canvas.drawRoundRect(10f, 9f, 14f, 21f, 1f, 1f, p)
                canvas.drawRoundRect(17f, 3f, 21f, 21f, 1f, 1f, p)
            }
            "bell" -> {
                val bell = Path().apply {moveTo(6f, 9f); cubicTo(6f, 1f, 18f, 1f, 18f, 9f); lineTo(18f, 16f); lineTo(21f, 19f); lineTo(3f, 19f); lineTo(6f, 16f); close()}
                canvas.drawPath(bell, p); canvas.drawArc(10f, 18f, 14f, 23f, 0f, 180f, false, p)
            }
            "moon" -> {val moon=Path().apply {moveTo(19f, 15f); cubicTo(13f, 18f, 6f, 11f, 9f, 4f); cubicTo(-1f, 10f, 6f, 26f, 19f, 15f); close()}; canvas.drawPath(moon,p)}
            "globe" -> {canvas.drawCircle(12f,12f,9f,p);canvas.drawOval(7f,3f,17f,21f,p);canvas.drawLine(3f,12f,21f,12f,p)}
            "help" -> {canvas.drawCircle(12f,12f,9f,p);canvas.drawArc(8f,5f,16f,14f,195f,210f,false,p);canvas.drawLine(12f,13f,12f,16f,p);canvas.drawPoint(12f,19f,p)}
            "chevron" -> {canvas.drawLine(9f,6f,15f,12f,p);canvas.drawLine(15f,12f,9f,18f,p)}
            "camera" -> {canvas.drawRoundRect(3f,7f,21f,19f,2f,2f,p);canvas.drawCircle(12f,13f,4f,p);canvas.drawLine(6f,7f,9f,4f,p);canvas.drawLine(9f,4f,15f,4f,p)}
            "logout" -> {
                canvas.drawLine(3f, 3f, 10f, 3f, p)
                canvas.drawLine(3f, 3f, 3f, 21f, p)
                canvas.drawLine(3f, 21f, 10f, 21f, p)
                canvas.drawLine(10f, 12f, 21f, 12f, p)
                canvas.drawLine(16f, 7f, 21f, 12f, p)
                canvas.drawLine(16f, 17f, 21f, 12f, p)
            }
            "coins" -> {
                canvas.drawCircle(16f, 8f, 6f, p)
                canvas.drawArc(2f, 10f, 14f, 22f, 25f, 290f, false, p)
                canvas.drawLine(16f, 5f, 16f, 11f, p)
            }
            "qr-code" -> {
                canvas.drawRoundRect(3f, 3f, 8f, 8f, 1f, 1f, p)
                canvas.drawRoundRect(16f, 3f, 21f, 8f, 1f, 1f, p)
                canvas.drawRoundRect(3f, 16f, 8f, 21f, 1f, 1f, p)
                canvas.drawLine(12f, 3f, 12f, 9f, p)
                canvas.drawLine(12f, 12f, 17f, 12f, p)
                canvas.drawLine(16f, 16f, 16f, 21f, p)
                canvas.drawLine(16f, 16f, 21f, 16f, p)
                canvas.drawLine(21f, 21f, 21f, 21f, p)
            }
            "award" -> {
                canvas.drawCircle(12f, 8f, 6f, p)
                val ribbon = Path().apply {
                    moveTo(8.5f, 13f); lineTo(7f, 21f); lineTo(12f, 18f)
                    lineTo(17f, 21f); lineTo(15.5f, 13f)
                }
                canvas.drawPath(ribbon, p)
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
