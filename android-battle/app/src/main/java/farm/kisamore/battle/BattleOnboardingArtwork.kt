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
 * Six lightweight vector scenes, with dedicated compact onboarding banners.
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
        if (height < width * .52f) {
            drawCompactBanner(canvas)
            return
        }
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
            2 -> viewer(canvas)
            3 -> resources(canvas)
            4 -> activity(canvas)
            5 -> trophy(canvas)
            else -> greenhouse(canvas)
        }
        canvas.restore()
    }

    /** A deliberately shallow 360×100 scene, not a squashed full-page drawing. */
    private fun drawCompactBanner(canvas: Canvas) {
        val scale = min(width / 360f, height / 100f)
        canvas.save()
        canvas.translate((width - 360f * scale) / 2f, (height - 100f * scale) / 2f)
        canvas.scale(scale, scale)
        val bg = color(dark)
        bg.shader = LinearGradient(0f, 0f, 360f, 100f,
            Color.rgb(36, 78, 53), Color.rgb(11, 44, 31), Shader.TileMode.CLAMP)
        canvas.drawRoundRect(2f, 2f, 358f, 98f, 17f, 17f, bg)
        bg.shader = null
        circle(canvas, 329f, 8f, 58f, moss, 22)
        circle(canvas, 32f, 105f, 55f, moss, 22)

        when (scene) {
            0 -> {
                rect(canvas, 28f, 15f, 306f, 72f, 11f, Color.rgb(22, 60, 39))
                label(canvas, "KISAMORE", 45f, 38f, 16f, mint, true)
                rect(canvas, 44f, 50f, 129f, 25f, 8f, moss)
                label(canvas, "JOIN  >", 71f, 67f, 12f, ink, true)
                rect(canvas, 182f, 50f, 134f, 25f, 8f, Color.rgb(61, 105, 76))
                label(canvas, "WATCH  >", 211f, 67f, 12f, ink, true)
            }
            1 -> {
                rect(canvas, 49f, 10f, 260f, 79f, 11f, Color.rgb(23, 58, 40))
                for (i in 0..1) {
                    rect(canvas, 57f, 19f + i * 33f, 30f, 27f, 7f, moss)
                    label(canvas, "C" + (i + 1), 64f, 38f + i * 33f, 14f, ink, true)
                }
                rect(canvas, 95f, 18f, 168f, 62f, 8f, Color.rgb(43, 94, 57))
                rect(canvas, 99f, 63f, 160f, 5f, 2f, amber)
                for (i in 0..3) {
                    val x = 105f + i * 38f
                    rect(canvas, x, 51f, 28f, 11f, 3f, Color.rgb(185, 119, 79))
                    line(canvas, x + 14f, 50f, x + 14f, 29f, mint, 2f)
                    leaf(canvas, x + 14f, 43f, 7f, true, mint)
                }
                listOf("24H", "3D").forEachIndexed { i, v ->
                    rect(canvas, 271f, 19f + i * 33f, 30f, 27f, 7f, moss)
                    label(canvas, v, 274f, 38f + i * 33f, 11f, ink, true)
                }
            }
            2 -> {
                rect(canvas, 46f, 10f, 268f, 80f, 11f, Color.rgb(16, 42, 30))
                rect(canvas, 58f, 18f, 244f, 37f, 6f, Color.rgb(46, 104, 60))
                for (i in 0..3) {
                    val x = 68f + i * 55f
                    line(canvas, x, 50f, x + 9f, 32f, mint, 3f)
                    leaf(canvas, x + 9f, 40f, 8f, true, moss)
                }
                listOf("−", "FIT", "+", "▶ 24H", "X").forEachIndexed { i, v ->
                    val w = if (i == 3) 65f else 39f
                    val x = listOf(62f, 106f, 151f, 195f, 265f)[i]
                    rect(canvas, x, 62f, w, 21f, 6f, moss)
                    label(canvas, v, x + 6f, 77f, 12f, ink, true)
                }
            }
            3 -> {
                listOf("WATER", "NUTRIENTS", "SHADE").forEachIndexed { i, v ->
                    val x = 23f + i * 110f
                    rect(canvas, x, 17f, 100f, 68f, 13f, Color.rgb(39, 93, 58))
                    circle(canvas, x + 17f, 39f, 7f,
                        if (i == 0) Color.rgb(127, 222, 246) else if (i == 1) amber else mint)
                    label(canvas, v, x + 31f, 43f, 12f, ink, true)
                    rect(canvas, x + 10f, 57f, 80f, 15f, 6f, moss)
                    label(canvas, "USE", x + 37f, 68f, 10f, ink, true)
                }
            }
            4 -> {
                rect(canvas, 32f, 13f, 295f, 76f, 12f, Color.rgb(29, 67, 42))
                label(canvas, "RECENT ACTIONS", 46f, 35f, 14f, ink, true)
                rect(canvas, 265f, 22f, 47f, 22f, 8f, moss)
                label(canvas, "ALL >", 269f, 37f, 11f, ink, true)
                for (i in 0..2) {
                    circle(canvas, 51f, 51f + i * 13f, 3f, mint)
                    rect(canvas, 63f, 49f + i * 13f, 110f - i * 14f, 5f, 2f, moss)
                }
                val ys = floatArrayOf(72f, 67f, 78f, 58f, 64f, 50f)
                for (i in 0..4) line(canvas, 195f + 23f * i, ys[i],
                    195f + 23f * (i + 1), ys[i + 1], mint, 2.5f)
            }
            else -> {
                rect(canvas, 53f, 20f, 76f, 62f, 9f, Color.rgb(215, 236, 201))
                rect(canvas, 65f, 34f, 52f, 7f, 3f, moss)
                for (i in 0..2) rect(canvas, 65f, 48f + i * 9f, 42f, 4f, 2f, moss)
                circle(canvas, 185f, 45f, 22f, amber)
                rect(canvas, 178f, 64f, 14f, 15f, 3f, amber)
                rect(canvas, 163f, 79f, 44f, 5f, 3f, amber)
                rect(canvas, 237f, 23f, 75f, 56f, 12f, Color.rgb(39, 90, 57))
                label(canvas, "KISA", 248f, 57f, 19f, ink, true)
            }
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

    /** Preview of the real fullscreen viewer controls without interactive actions. */
    private fun viewer(c: Canvas) {
        rect(c, 67f, 13f, 226f, 284f, 24f, Color.rgb(7, 17, 12))
        rect(c, 77f, 22f, 206f, 32f, 8f, Color.rgb(32, 65, 44))
        label(c, "PHOTO", 90f, 43f, 14f, ink, true)
        rect(c, 207f, 27f, 45f, 20f, 7f, moss)
        label(c, "SHARE", 211f, 41f, 10f, ink, true)
        label(c, "×", 264f, 43f, 24f, ink, true)
        rect(c, 80f, 61f, 200f, 150f, 12f, Color.rgb(29, 73, 47))
        rect(c, 92f, 160f, 176f, 8f, 4f, Color.rgb(147, 113, 80))
        repeat(4) { i ->
            val x = 103f + i * 41f
            rect(c, x, 141f, 28f, 18f, 5f, Color.rgb(172, 120, 77))
            line(c, x + 14f, 142f, x + 14f, 115f - i * 3f, moss)
            leaf(c, x + 13f, 125f - i * 3f, 10f, true, mint)
            leaf(c, x + 13f, 117f - i * 3f, 10f, false, mint)
        }
        rect(c, 96f, 174f, 59f, 8f, 4f, Color.rgb(20, 42, 30))
        rect(c, 105f, 218f, 40f, 29f, 8f, moss)
        rect(c, 150f, 218f, 60f, 29f, 8f, moss)
        rect(c, 215f, 218f, 40f, 29f, 8f, moss)
        label(c, "−", 118f, 239f, 24f, ink)
        label(c, "FIT", 166f, 238f, 13f, ink, true)
        label(c, "+", 228f, 239f, 21f, ink)
        val b = listOf("PHOTO","24H","3D","ALL")
        b.forEachIndexed { i, text ->
            rect(c, 77f + i * 52f, 256f, 47f, 27f, 7f, if(i==0) moss else Color.rgb(42, 80, 52))
            label(c, text, 84f + i * 52f, 274f, 10f, ink, true)
        }
    }

    /** Recent activity and chart period controls shown below player commands. */
    private fun activity(c: Canvas) {
        rect(c, 28f, 33f, 304f, 245f, 24f, Color.rgb(18, 45, 30))
        label(c, "RECENT ACTIONS", 46f, 67f, 17f, ink, true)
        rect(c, 252f, 45f, 58f, 29f, 12f, moss)
        label(c, "ALL ›", 262f, 64f, 13f, ink, true)
        val times = listOf("09:40","11:15","12:05")
        times.forEachIndexed { i, time ->
            val y = 91f + i * 39f
            circle(c, 52f, y, 11f, if(i==0) mint else moss)
            label(c, time, 71f, y + 4f, 12f, ink)
            rect(c, 154f, y - 7f, 119f - i * 17f, 14f, 7f,
                Color.rgb(70, 119, 78))
        }
        label(c, "ACTIVITY", 46f, 218f, 16f, ink, true)
        listOf("24H","3D","7D").forEachIndexed { i, name ->
            rect(c, 151f + i * 53f, 197f, 46f, 29f, 10f,
                if(i==1) moss else Color.rgb(39, 78, 53))
            label(c, name, 160f + i * 53f, 217f, 13f, ink, true)
        }
        val values = listOf(251f,242f,255f,240f,249f,236f,244f)
        for(i in 0 until values.lastIndex) {
            line(c, 48f + i * 42f, values[i], 48f + (i+1) * 42f,
                values[i+1], mint, 3f)
        }
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
