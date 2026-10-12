package farm.kisamore.battle

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.google.zxing.BarcodeFormat
import com.google.zxing.MultiFormatWriter
import com.google.zxing.common.BitMatrix
import java.text.SimpleDateFormat
import java.util.Locale

/** Authorized-user battle history based on the approved Figma light/dark layouts. */
internal class BattleHistoryScreen(
    private val host: Activity,
    private val battles: List<Battle>,
    private val api: ApiClient,
    private val onViewBattle: (Battle) -> Unit,
    private val onPhoto: (Battle) -> Unit,
    private val onVideo: (String?) -> Unit,
    private val onCertificate: (String) -> Unit,
    private val onCurrentBattle: () -> Unit
) : ScrollView(host) {
    private val dark = host.getSharedPreferences("battle_settings", 0).getBoolean("dark_mode", false)
    private val back = color(if (dark) "#101A14" else "#F8F9F6")
    private val surface = color(if (dark) "#1B2A22" else "#FFFFFF")
    private val textColor = color(if (dark) "#F2F6F2" else "#24352A")
    private val muted = color(if (dark) "#B6C1B6" else "#6B7268")
    private val green = color(if (dark) "#8CC89E" else "#4A7C59")

    init {
        setBackgroundColor(back)
        isFillViewport = true
        val body = LinearLayout(host).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(29), dp(16), dp(28))
        }
        addView(body)
        body.addView(label("История", 27f, true), LinearLayout.LayoutParams(-1, dp(40)))
        body.addView(label("Ваши завершённые соревнования", 13f), LinearLayout.LayoutParams(-1, dp(35)))
        val completed = battles.filter { it.status == "finished" && it.mine != null }
            .sortedByDescending { it.finishedAt ?: it.createdAt ?: "" }
        if (completed.isEmpty()) {
            val card = panel().apply {
                gravity = Gravity.CENTER
                setPadding(dp(22), dp(36), dp(22), dp(26))
            }
            val circle = LinearLayout(host).apply {
                gravity = Gravity.CENTER
                background = rounded(if (dark) "#273E2F" else "#EAF2EA", 54)
                addView(BattleTabGlyph(host, "history", green),
                    LinearLayout.LayoutParams(dp(58), dp(58)))
            }
            card.addView(circle, LinearLayout.LayoutParams(dp(108), dp(108)))
            card.addView(label("Пока нет завершённых битв", 17f, true).apply {
                gravity = Gravity.CENTER
                setPadding(0, dp(22), 0, dp(9))
            })
            card.addView(label("Когда ваша битва закончится, здесь появятся результаты, фотографии, таймлапсы и цифровой диплом.", 14f).apply {
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(-1, dp(85)))
            val button = label("Смотреть текущую битву", 14f, true).apply {
                gravity = Gravity.CENTER
                setTextColor(Color.WHITE)
                background = rounded("#4A7C59", 12)
                setOnClickListener { onCurrentBattle() }
            }
            card.addView(button, LinearLayout.LayoutParams(-1, dp(44)))
            body.addView(card, LinearLayout.LayoutParams(-1, dp(382)))
        } else {
            val wins = completed.count { it.mine?.isWinner == true }
            val stats = panel().apply { orientation = LinearLayout.HORIZONTAL }
            listOf("ЗАВЕРШЕНО" to completed.size, "ПОБЕДЫ" to wins,
                "ДИПЛОМЫ" to completed.count { it.mine?.certificateUrl != null }).forEach { (name, count) ->
                val col = LinearLayout(host).apply { orientation = LinearLayout.VERTICAL }
                col.addView(label(name, 10f, true))
                col.addView(label(count.toString(), 29f, true).apply { setTextColor(green) })
                stats.addView(col, LinearLayout.LayoutParams(0, dp(62), 1f))
            }
            body.addView(stats, LinearLayout.LayoutParams(-1, dp(85)))
            body.addView(label("Завершённые битвы", 18f, true).apply {
                setPadding(dp(2), dp(22), 0, dp(12))
            })
            completed.forEach { battle ->
                val entry = battle.mine ?: return@forEach
                val card = panel()
                val first = LinearLayout(host).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = Gravity.CENTER_VERTICAL
                }
                val thumb = ImageView(host).apply {
                    scaleType = ImageView.ScaleType.CENTER_CROP
                    background = rounded(if (dark) "#273E2F" else "#E8EEE7", 12)
                }
                first.addView(thumb, LinearLayout.LayoutParams(dp(78), dp(82)))
                val column = LinearLayout(host).apply {
                    orientation = LinearLayout.VERTICAL
                    setPadding(dp(14), 0, dp(4), 0)
                }
                column.addView(label(battle.localizedPlantName(AppLanguage(host).code), 16f, true))
                column.addView(label(if (entry.isWinner) "Победа" else "Участие", 13f, true).apply {
                    setTextColor(green)
                })
                column.addView(label("Завершено: " + formatDate(battle.finishedAt), 12f))
                first.addView(column, LinearLayout.LayoutParams(0, -2, 1f))
                val certificate = entry.certificateUrl?.let { api.absolute(it) }
                    ?: api.absolute("/api/v1/battle-certificate/${entry.id}")
                if (certificate != null) {
                    val qr = ImageView(host).apply {
                        contentDescription = "QR-код диплома"
                        setImageBitmap(makeQr(certificate))
                        setOnClickListener { onCertificate(certificate) }
                    }
                    first.addView(qr, LinearLayout.LayoutParams(dp(50), dp(50)))
                }
                card.addView(first)
                entry.photoUrl?.let { relative ->
                    api.absolute(relative)?.let { url ->
                        PhotoFrameCache.current(url)?.let { thumb.setImageBitmap(it) }
                        Thread {
                            val bitmap = api.loadBitmap(url)
                            if (bitmap != null) {
                                PhotoFrameCache.remember(url, bitmap)
                                host.runOnUiThread {
                                    if (!host.isFinishing && thumb.isAttachedToWindow) thumb.setImageBitmap(bitmap)
                                }
                            }
                        }.start()
                    }
                }
                val actions = LinearLayout(host).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = Gravity.CENTER_VERTICAL
                    setPadding(0, dp(14), 0, 0)
                }
                action(actions,"Фото") { onPhoto(battle) }
                action(actions,"Таймлапс") { onVideo(entry.timelapse3dUrl ?: entry.timelapse24hUrl) }
                if (certificate != null) action(actions,"Диплом") { onCertificate(certificate) }
                card.addView(actions)
                body.addView(card, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(12) })
            }
        }
    }
    private fun action(row: LinearLayout, title: String, callback: () -> Unit) {
        row.addView(label(title, 12f, true).apply {
            setTextColor(green)
            gravity = Gravity.CENTER
            setOnClickListener { callback() }
        }, LinearLayout.LayoutParams(0, dp(32), 1f))
    }
    private fun label(value: String, size: Float, strong: Boolean = false) = TextView(host).apply {
        text = value
        textSize = size
        setTextColor(if (strong) textColor else muted)
        if (strong) setTypeface(typeface, Typeface.BOLD)
        includeFontPadding = false
    }
    private fun panel() = LinearLayout(host).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(14), dp(14), dp(14), dp(14))
        background = rounded(if (dark) "#1B2A22" else "#FFFFFF", 18)
    }
    private fun rounded(hex: String, radius: Int) = GradientDrawable().apply {
        setColor(color(hex)); cornerRadius = dp(radius).toFloat()
    }
    private fun color(hex: String) = Color.parseColor(hex)
    private fun dp(n: Int) = (n * resources.displayMetrics.density).toInt()
    private fun formatDate(raw: String?): String {
        if (raw.isNullOrBlank()) return "—"
        return raw.take(10)
    }
    private fun makeQr(data: String): Bitmap? = runCatching {
        val bits: BitMatrix = MultiFormatWriter().encode(data, BarcodeFormat.QR_CODE, 150, 150)
        Bitmap.createBitmap(150, 150, Bitmap.Config.ARGB_8888).apply {
            for (x in 0 until 150) for (y in 0 until 150)
                setPixel(x, y, if (bits[x,y]) Color.BLACK else Color.WHITE)
        }
    }.getOrNull()
}
