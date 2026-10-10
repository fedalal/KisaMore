package farm.kisamore.battle

import android.app.Activity
import android.content.res.Configuration
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.VideoView

/**
 * Welcome screen for signed-out visitors and users without an active entry.
 * Battle counts, image, and video addresses are sourced from the public API.
 * The UI deliberately has no sample battles or fictitious availability.
 */
class GuestHomeScreen(
    private val activity: Activity,
    private val api: ApiClient,
    private val language: AppLanguage,
    private val battles: List<Battle>,
    private val genericClips: List<HomeClip>,
    private val onJoin: (Battle) -> Unit,
    private val onWatch: () -> Unit
) {
    private val isDark = activity.getSharedPreferences("battle_settings", Activity.MODE_PRIVATE)
        .getBoolean("dark_mode", false)
    private val background = color(if (isDark) "#101A14" else "#F8F9F6")
    private val cardColor = color(if (isDark) "#1A2C21" else "#FFFFFF")
    private val ink = color(if (isDark) "#EDF4EC" else "#233B2D")
    private val secondary = color(if (isDark) "#ADBCB0" else "#718073")
    private val accent = color(if (isDark) "#8FC69A" else "#4A7C59")
    private val border = color(if (isDark) "#375141" else "#E0E8DF")
    private val chip = color(if (isDark) "#294E36" else "#EAF3E9")
    private val primary = color(if (isDark) "#477D5A" else "#4A7C59")
    private var playlist: GuestTimelapseQueue? = null
    var rootView: View? = null
        private set

    fun create(): View {
        val scroll = ScrollView(activity).apply {
            setBackgroundColor(this@GuestHomeScreen.background)
            isFillViewport = true
            clipToPadding = false
            isVerticalScrollBarEnabled = false
        }
        val column = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(9), dp(16), dp(14))
        }
        scroll.addView(column, FrameLayout.LayoutParams(-1, -2))

        val brand = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        brand.addView(ImageView(activity).apply {
            setImageResource(R.drawable.ic_sprout_outline)
            imageTintList = ColorStateList.valueOf(accent)
        }, LinearLayout.LayoutParams(dp(24), dp(24)))
        brand.addView(text("KisaMore", 20f, ink, true).apply {
            setPadding(dp(7), 0, dp(8), 0)
        })
        brand.addView(text("BATTLE", 10f, accent, true),
            LinearLayout.LayoutParams(0, -2, 1f))
        brand.addView(text(
            if (api.hasSession()) (api.currentUser?.displayName ?: t("Игрок")) else t("ГОСТЬ"),
            10f, accent, true
        ).apply {
            setPadding(dp(12), dp(6), dp(12), dp(6))
            background = shape(chip, 16)
            maxLines = 1
        })
        column.addView(brand)
        column.addView(space(10))
        column.addView(text(t("Битва живых растений"), 22f, ink, true).apply {
            maxLines = 1
            setAutoSizeTextTypeUniformWithConfiguration(
                18, 22, 1, android.util.TypedValue.COMPLEX_UNIT_SP
            )
        })
        column.addView(space(5))
        column.addView(text(t("Настоящие растения. Твои решения."), 12f, secondary))
        column.addView(space(10))
        // Keep both actions in view on smaller phones without sacrificing scroll support.
        val screenHeightDp = activity.resources.displayMetrics.heightPixels /
            activity.resources.displayMetrics.density
        val previewHeightDp = (screenHeightDp * 0.24f).toInt().coerceIn(158, 194)
        column.addView(makeVideoPreview(), LinearLayout.LayoutParams(-1, dp(previewHeightDp)))
        column.addView(space(8))
        column.addView(makeUpcomingCard())
        column.addView(space(8))
        column.addView(makeWatchButton(), LinearLayout.LayoutParams(-1, dp(42)))
        rootView = scroll
        return scroll
    }

    fun release() {
        playlist?.release()
        playlist = null
    }

    private fun makeVideoPreview(): View {
        val choices = HomeBattleSelector.videoOptions(battles, genericClips)
        val posterBattle = choices.firstOrNull()?.battle
            ?: battles.firstOrNull { it.status == "growing" }
            ?: battles.firstOrNull()
        val frame = FrameLayout(activity).apply {
            background = shape(color("#1E4430"), 18)
            clipToOutline = true
        }
        val poster = ImageView(activity).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            setBackgroundColor(color("#173326"))
        }
        frame.addView(poster, FrameLayout.LayoutParams(-1, -1))
        val posterPath = choices.firstOrNull()?.posterUrl ?: posterBattle?.rackPhotoUrl
            ?: posterBattle?.plantId?.let { plantPhotoPath(it) }
        fillPhoto(poster, posterPath)

        // A GONE VideoView has no Surface, so MediaPlayer never reaches
        // onPrepared and autoplay silently fails. Keep it attached and visible,
        // with the poster on top until the first playable video is prepared.
        val video = VideoView(activity).apply {
            visibility = View.VISIBLE
            setBackgroundColor(Color.TRANSPARENT)
        }
        frame.addView(video, FrameLayout.LayoutParams(-1, -1))
        poster.bringToFront()

        val top = LinearLayout(activity).apply {
            gravity = Gravity.CENTER_VERTICAL
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(13), dp(11), dp(12), 0)
        }
        top.addView(text(t("ТАЙМЛАПС"), 10f, Color.WHITE, true).apply {
            setPadding(dp(10), dp(5), dp(10), dp(5))
            background = shape(color("#356448"), 16)
        })
        top.addView(text(
            choices.firstOrNull()?.let {
                if (it.isWholeBattle) t("Прошлая битва") else t("Рост растения")
            } ?: t("Как растут растения"),
            11f, Color.WHITE, true
        ).apply { setPadding(dp(11), 0, 0, 0) })
        frame.addView(top, FrameLayout.LayoutParams(-1, -2, Gravity.TOP))

        val play = TextView(activity).apply {
            text = "▶"
            textSize = 25f
            gravity = Gravity.CENTER
            setTextColor(color("#386D4A"))
            background = shape(color("#F5FBF3"), 50)
        }
        frame.addView(play, FrameLayout.LayoutParams(dp(58), dp(58), Gravity.CENTER))
        // Autoplay starts on its own: don't imply the user must tap Play.
        play.visibility = View.GONE

        // No bottom caption overlay: all video pixels remain unobstructed.
        top.bringToFront()
        play.bringToFront()

        val queue = GuestTimelapseQueue(activity, api, choices, video, poster, play)
        playlist = queue
        video.setOnClickListener { queue.onVideoPressed() }
        play.setOnClickListener { queue.onPlayPressed() }
        // Show the latest rack photo only during the initial MP4 download.
        // Subsequent MP4s are prefetched while the current one plays.
        video.post { queue.start() }
        return frame
    }

    private fun makeUpcomingCard(): View {
        val card = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = shape(cardColor, 18, border)
        }
        val upcoming = HomeBattleSelector.nextOpenBattle(battles)
        val top = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        top.addView(text(t("БЛИЖАЙШАЯ БИТВА"), 11f, ink, true),
            LinearLayout.LayoutParams(0, -2, 1f))
        if (upcoming != null) {
            top.addView(text(t("● Набор открыт"), 10f, accent, false).apply {
                setPadding(dp(9), dp(5), dp(9), dp(5))
                background = shape(chip, 16)
            })
        }
        card.addView(top)
        card.addView(space(10))
        if (upcoming == null) {
            card.addView(text(t("Пока нет открытых битв"), 15f, ink, true))
            card.addView(space(5))
            card.addView(text(t("Новые битвы появятся здесь. Пока можно смотреть другие."), 12f, secondary))
            card.addView(space(11))
            card.addView(makeActionButton(t("Смотреть битвы"), false) { onWatch() },
                LinearLayout.LayoutParams(-1, dp(46)))
            return card
        }

        val plant = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val photo = ImageView(activity).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = shape(chip, 13)
            clipToOutline = true
            setImageResource(R.drawable.ic_sprout_outline)
            imageTintList = ColorStateList.valueOf(accent)
        }
        plant.addView(photo, LinearLayout.LayoutParams(dp(58), dp(58)))
        if (!upcoming.plantId.isNullOrBlank()) {
            photo.imageTintList = null
            fillPhoto(photo, plantPhotoPath(upcoming.plantId))
        }
        val detail = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), 0, 0, 0)
        }
        detail.addView(text(upcoming.plantName, 18f, ink, true).apply {
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
        })
        detail.addView(text(t("Один сорт · ") + upcoming.maxEntries + t(" игроков"), 11f, secondary))
        detail.addView(text(t("Старт после набора участников"), 11f, secondary))
        plant.addView(detail, LinearLayout.LayoutParams(0, -2, 1f))
        card.addView(plant)
        card.addView(space(10))

        val stats = LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        stats.addView(text(
            upcoming.remainingEntries.toString() + " " + t("мест свободно"),
            14f, accent, true
        ), LinearLayout.LayoutParams(0, -2, 1f))
        stats.addView(text(
            upcoming.entriesCount.toString() + " " + t("из") + " " + upcoming.maxEntries + " " + t("занято"),
            11f, secondary
        ))
        card.addView(stats)
        card.addView(space(7))

        val bars = LinearLayout(activity).apply { orientation = LinearLayout.HORIZONTAL }
        val total = upcoming.maxEntries.coerceIn(1, 12)
        val occupied = (total - upcoming.remainingEntries).coerceIn(0, total)
        repeat(total) { i ->
            val segment = View(activity).apply {
                background = shape(
                    if (i < occupied) accent else color(if (isDark) "#344A3A" else "#E6ECE5"),
                    6
                )
            }
            bars.addView(segment, LinearLayout.LayoutParams(0, dp(8), 1f).apply {
                if (i > 0) leftMargin = dp(5)
            })
        }
        card.addView(bars)
        card.addView(space(11))
        card.addView(makeActionButton(t("Присоединиться к битве"), true) {
            onJoin(upcoming)
        }, LinearLayout.LayoutParams(-1, dp(46)))
        card.addView(space(9))
        card.addView(text(
            upcoming.winnerRewardKisa.toString() + " Kisa " + t("победителю · диплом каждому"),
            11f, secondary
        ))
        return card
    }

    private fun makeWatchButton(): View = makeActionButton(t("Смотреть битвы без входа"), false) {
        onWatch()
    }

    private fun makeActionButton(label: String, filled: Boolean, action: () -> Unit): View {
        return LinearLayout(activity).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            background = if (filled) shape(primary, 12) else shape(cardColor, 12, border)
            if (!filled) {
                addView(ImageView(activity).apply {
                    setImageResource(R.drawable.ic_eye_outline)
                    imageTintList = ColorStateList.valueOf(ink)
                }, LinearLayout.LayoutParams(dp(19), dp(19)).apply { rightMargin = dp(8) })
            }
            addView(text(label, if (filled) 15f else 13f, if (filled) Color.WHITE else ink, true))
            if (filled) addView(ImageView(activity).apply {
                setImageResource(R.drawable.ic_arrow_right_outline)
                imageTintList = ColorStateList.valueOf(Color.WHITE)
            }, LinearLayout.LayoutParams(dp(19), dp(19)).apply { leftMargin = dp(12) })
            setOnClickListener { action() }
            isClickable = true
        }
    }

    private fun fillPhoto(target: ImageView, path: String?) {
        val url = api.absolute(path) ?: return
        Thread {
            val bitmap = runCatching { api.loadBitmap(url) }.getOrNull()
            if (bitmap != null) activity.runOnUiThread {
                if (!activity.isFinishing && !activity.isDestroyed) target.setImageBitmap(bitmap)
            }
        }.start()
    }

    private fun plantPhotoPath(id: String) =
        "/api/v1/public/plants/" + Uri.encode(id) + "/image"

    private fun text(
        value: String,
        size: Float,
        foreground: Int,
        bold: Boolean = false
    ): TextView = TextView(activity).apply {
        text = value
        textSize = size
        setTextColor(foreground)
        includeFontPadding = false
        if (bold) setTypeface(typeface, Typeface.BOLD)
    }

    private fun space(height: Int) = View(activity).apply {
        layoutParams = LinearLayout.LayoutParams(1, dp(height))
    }

    private fun shape(fill: Int, radius: Int, line: Int? = null) = GradientDrawable().apply {
        cornerRadius = dp(radius).toFloat()
        setColor(fill)
        if (line != null) setStroke(dp(1), line)
    }

    private fun t(value: String) = language.t(value)
    private fun dp(value: Int) = (value * activity.resources.displayMetrics.density).toInt()
    private fun color(value: String) = Color.parseColor(value)
}
