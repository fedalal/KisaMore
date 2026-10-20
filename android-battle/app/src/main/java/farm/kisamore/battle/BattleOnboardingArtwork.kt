package farm.kisamore.battle

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.view.View
import kotlin.math.min

/**
 * Four lightweight, original vector scenes that scale to any Android display.
 * Assets are built into the app — no network, image cropping or remote files.
 */
internal class BattleOnboardingArtwork(
    context: Context,
    private val scene: Int
) : View(context) {
    private val brush = Paint(Paint.ANTI_ALIAS_FLAG)
    private val ink = Color.rgb(229, 251, 225)
    private val mint = Color.rgb(146, 236, 163)
    private val moss = Color.rgb(71, 168, 109)
    private val dark = Color.rgb(9, 34, 24)
    private val amber = Color.rgb(246, 201, 105)

    private fun color(c: Int, alpha: Int = 255): Paint =
        brush.apply {
            reset()
            isAntiAlias = true
            style = Paint.Style.FILL
            shader = null
            this.color = c
            this.alpha = alpha
        }

    private fun rect(canvas: Canvas, x: Float, y: Float, w: Float, h: Float,
                     r: Float, tint: Int, alpha: Int = 255) {
        canvas.drawRoundRect(x, y, x + w, y + h, r, r, color(tint, alpha))
    }

    private fun circle(canvas: Canvas, x: Float, y: Float, radius: Float,
                       tint: Int, alpha: Int = 255) =
        canvas.drawCircle(x, y, radius, color(tint, alpha))

    private fun line(canvas: Canvas, x: Float, y: Float, x2: Float, y2: Float,
                     tint: Int, width: Float = 3f) {
        val p = color(tint)
        p.style = Paint.Style.STROKE
        p.strokeWidth = width
        p.strokeCap = Paint.Cap.ROUND
        canvas.drawLine(x, y, x2, y2, p)
        p.style = Paint.Style.FILL
    }

    private fun label(canvas: Canvas, text: String, x: Float, y: Float,
                      sp: Float, tint: Int, bold: Boolean = false) {
        val p = color(tint)
        p.textSize = sp
        p.typeface = if (bold) android.graphics.Typeface.create("sans-serif-medium", 0)
                     else android.graphics.Typeface.create("sans-serif", 0)
        canvas.drawText(text, x, y, p)
    }

    private fun leaf(canvas: Canvas, x: Float, y: Float,
                     size: Float, left: Boolean, tint: Int) {
        val sign = if (left) -1f else 1f
        val path = Path().apply {
            moveTo(x, y)
            cubicTo(x + 1f * sign * size, y - size * 0.8f,
                x + sign * size * 0.9f, y - size * 1.7f,
                x + sign * size * 1.6f, y - size * 1.6f)
            cubicTo(x + sign * size * 1.7f, y - size * 0.6f,
                x + sign * size * 0.9f, y - size * 0.2f, x, y)
            close()
        }
        canvas.drawPath(path, color(tint))
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val scale = min(width / 360f, height / 310f)
        canvas.save()
        canvas.translate((width - 360f * scale) / 2f, (height - 310f * scale) / 2f)
        canvas.scale(scale, scale)
        val bg = color(dark)
        bg.shader = LinearGradient(0f, 0f, 360f, 320f,
            Color.rgb(33, 72, 50), Color.rgb(12, 46, 33), Shader.TileMode.CLAMP)
        canvas.drawRoundRect(3f, 3f, 357f, 307f, 30f, 30f, bg)
        bg.shader = null
        circle(canvas, 296f, 45f, 90f, moss, 28)
        circle(canvas, 56f, 255f, 83f, moss, 18)
        for (i in 0..12) {
            circle(canvas, 26f + (i * 51) % 302, 24f + (i * 41) % 248,
                if (i % 3 == 0) 2.4f else 1.4f, ink, 90)
        }
        when (scene) {
            0 -> greenhouse(canvas)
            1 -> camera(canvas)
            2 -> resources(canvas)
            else -> trophy(canvas)
        }
        canvas.restore()
    }

    private fun greenhouse(c: Canvas) {
        // Sun and curved greenhouse glass.
        circle(c, 285f, 62f, 23f, amber, 220)
        circle(c, 285f, 62f, 37f, amber, 28)
        val dome = Path().apply {
            moveTo(50f, 230f); lineTo(50f, 116f)
            cubicTo(50f, 22f, 310f, 22f, 310f, 116f)
            lineTo(310f, 230f)
        }
        val frame = color(Color.rgb(105, 187, 139))
        frame.style = Paint.Style.STROKE
        frame.strokeWidth = 4f
        frame.strokeCap = Paint.Cap.ROUND
        c.drawPath(dome, frame)
        frame.strokeWidth = 1.5f; frame.alpha = 125
        c.drawLine(180f, 52f, 180f, 235f, frame)
        c.drawLine(53f, 142f, 306f, 142f, frame)
        c.drawLine(100f, 70f, 100f, 238f, frame)
        c.drawLine(260f, 70f, 260f, 238f, frame)
        // Two shelf levels with six real growing containers.
        rect(c, 38f, 231f, 284f, 12f, 5f, Color.rgb(81, 118, 91))
        rect(c, 40f, 248f, 280f, 7f, 4f, Color.rgb(42, 92, 65))
        repeat(6) { i ->
            val x = 46f + i * 46f
            rect(c, x, 208f, 38f, 23f, 5f, Color.rgb(204, 153, 101))
            rect(c, x + 2f, 209f, 34f, 5f, 3f, Color.rgb(114, 73, 49))
            val stem = 207f - (i % 3) * 7f
            line(c, x + 19f, 209f, x + 19f, stem - 23f, moss, 3f)
            leaf(c, x + 19f, stem - 10f, 12f, true, mint)
            leaf(c, x + 19f, stem - 18f, 12f, false, moss)
        }
        rect(c, 101f, 264f, 158f, 27f, 13f, Color.rgb(33, 84, 57))
        label(c, "6   •   LIVE GREENHOUSE", 111f, 283f, 12f, ink, true)
    }

    private fun camera(c: Canvas) {
        // Camera preview device with tiny rack, replay controls and play sign.
        rect(c, 83f, 19f, 194f, 267f, 27f, Color.rgb(1, 21, 14))
        rect(c, 89f, 26f, 182f, 253f, 23f, Color.rgb(21, 53, 36))
        rect(c, 146f, 34f, 68f, 6f, 3f, Color.rgb(70, 104, 78))
        label(c, "LIVE  •  RACK 1", 107f, 68f, 13f, mint, true)
        rect(c, 105f, 85f, 150f, 128f, 10f, Color.rgb(37, 80, 48))
        rect(c, 112f, 169f, 136f, 8f, 3f, Color.rgb(180, 148, 104))
        repeat(3) { i ->
            val x = 119f + i * 44f
            rect(c, x, 147f, 34f, 20f, 4f, Color.rgb(159, 107, 69))
            line(c, x + 17f, 145f, x + 17f, 120f - 5f * i, mint, 2.5f)
            leaf(c, x + 17f, 123f - 4f * i, 10f, true, moss)
            leaf(c, x + 17f, 129f - 4f * i, 9f, false, mint)
        }
        circle(c, 180f, 148f, 29f, Color.rgb(5, 34, 20), 210)
        val play = Path().apply {
            moveTo(172f, 136f); lineTo(191f, 148f)
            lineTo(172f, 160f); close()
        }
        c.drawPath(play, color(Color.WHITE))
        rect(c, 105f, 225f, 46f, 27f, 10f, Color.rgb(55, 114, 75))
        rect(c, 157f, 225f, 45f, 27f, 10f, Color.rgb(55, 114, 75))
        rect(c, 208f, 225f, 47f, 27f, 10f, Color.rgb(55, 114, 75))
        label(c, "24H", 116f, 244f, 12f, ink, true)
        label(c, "3D", 172f, 244f, 12f, ink, true)
        label(c, "ALL", 216f, 244f, 12f, ink, true)
        rect(c, 45f, 120f, 50f, 50f, 15f, Color.rgb(47, 100, 70))
        circle(c, 70f, 145f, 13f, mint)
        circle(c, 70f, 145f, 7f, dark)
        rect(c, 261f, 98f, 56f, 52f, 15f, Color.rgb(47, 100, 70))
        val rec = color(amber); rec.style = Paint.Style.STROKE; rec.strokeWidth = 3f
        c.drawCircle(289f, 124f, 13f, rec)
        circle(c, 289f, 124f, 5f, amber)
    }

    private fun resources(c: Canvas) {
        val xs = listOf(33f, 129f, 225f)
        val panels = listOf(Color.rgb(49, 108, 132), Color.rgb(92, 112, 59),
            Color.rgb(109, 82, 130))
        xs.forEachIndexed { i, x ->
            rect(c, x, 74f - if (i == 1) 17f else 0f,
                100f, 160f, 21f, panels[i])
            rect(c, x + 9f, 87f - if (i == 1) 17f else 0f,
                82f, 72f, 15f, Color.WHITE, 22)
            val yy = 124f - if (i == 1) 17f else 0f
            when (i) {
                0 -> {
                    val drop = Path().apply {
                        moveTo(x + 50f, yy - 35f)
                        cubicTo(x + 28f, yy - 7f, x + 28f, yy + 3f, x + 50f, yy + 14f)
                        cubicTo(x + 72f, yy + 4f, x + 73f, yy - 7f, x + 50f, yy - 35f)
                    }
                    c.drawPath(drop, color(Color.rgb(150, 228, 250)))
                }
                1 -> {
                    line(c, x + 50f, yy + 16f, x + 50f, yy - 25f, mint, 4f)
                    leaf(c, x + 49f, yy - 7f, 19f, true, mint)
                    leaf(c, x + 51f, yy - 17f, 17f, false, ink)
                }
                2 -> {
                    circle(c, x + 50f, yy - 8f, 24f, amber)
                    circle(c, x + 62f, yy - 17f, 25f, panels[i])
                    circle(c, x + 37f, yy - 22f, 3f, ink)
                }
            }
            repeat(4) { j ->
                rect(c, x + 14f + j * 18f, 187f - if (i == 1) 17f else 0f,
                    12f, 6f, 3f, if (j < 3 - i) mint else Color.rgb(109, 138, 118))
            }
        }
        rect(c, 68f, 246f, 224f, 37f, 17f, Color.rgb(34, 88, 61))
        label(c, "WATER", 82f, 269f, 12f, ink, true)
        label(c, "•", 148f, 269f, 14f, mint, true)
        label(c, "NUTRIENTS", 162f, 269f, 12f, ink, true)
    }

    private fun trophy(c: Canvas) {
        rect(c, 47f, 92f, 119f, 169f, 15f, Color.rgb(220, 242, 208))
        rect(c, 59f, 105f, 95f, 11f, 5f, Color.rgb(81, 143, 93))
        line(c, 61f, 130f, 149f, 130f, Color.rgb(119, 167, 124), 2f)
        line(c, 61f, 140f, 138f, 140f, Color.rgb(119, 167, 124), 2f)
        repeat(5) { y ->
            repeat(5) { x ->
                if ((x * 3 + y * 7) % 4 != 0)
                    rect(c, 69f + x * 12f, 161f + y * 12f,
                        8f, 8f, 1.5f, Color.rgb(34, 85, 53))
            }
        }
        rect(c, 63f, 230f, 90f, 11f, 4f, Color.rgb(105, 174, 115))
        // Gold cup with two side handles, stem and base.
        val cup = Path().apply {
            moveTo(204f, 92f); lineTo(292f, 92f)
            lineTo(283f, 162f)
            cubicTo(278f, 184f, 217f, 185f, 213f, 162f)
            close()
        }
        c.drawPath(cup, color(amber))
        val handle = color(amber)
        handle.style = Paint.Style.STROKE; handle.strokeWidth = 11f
        c.drawArc(RectF(185f, 105f, 228f, 153f), 85f, 190f, false, handle)
        c.drawArc(RectF(271f, 105f, 310f, 153f), -98f, 190f, false, handle)
        circle(c, 248f, 131f, 20f, Color.rgb(235, 174, 66))
        leaf(c, 249f, 144f, 14f, true, ink)
        leaf(c, 248f, 135f, 13f, false, Color.WHITE)
        rect(c, 243f, 179f, 10f, 31f, 3f, amber)
        rect(c, 218f, 211f, 61f, 13f, 5f, amber)
        rect(c, 204f, 225f, 89f, 24f, 8f, Color.rgb(194, 139, 60))
        label(c, "KISA", 224f, 242f, 14f, dark, true)
        circle(c, 74f, 67f, 20f, mint, 190)
        circle(c, 307f, 265f, 14f, amber, 200)
    }
}
