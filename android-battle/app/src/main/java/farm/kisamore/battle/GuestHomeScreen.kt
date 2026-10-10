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
    private val isDark = (activity.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    private val background = color(if (isDark) "#101A14" else "#F8F9F6")
    private val cardColor = color(if (isDark) "#1A2C21" else "#FFFFFF")
    private val ink = color(if (isDark) "#EDF4EC" else "#233B2D")
    private val secondary = color(if (isDark) "#ADBCB0" else "#718073")
    private val accent = color(if (isDark) "#8FC69A" else "#4A7C59")
    private val border = color(if (isDark) "#375141" else "#E0E8DF")
    private val chip = color(if (isDark) "#294E36" else "#EAF3E9")
    private val primary = color(if (isDark) "#477D5A" else "#4A7C59")
    private var movie: VideoView? = null
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
        column.addView(space(20))
        column.addView(text(t("ЖИВАЯ БИТВА РАСТЕНИЙ"), 11f, accent, true))
        column.addView(space(5))
        column.addView(text(t("Выращивай. Соревнуйся.\nПобеждай."), 27f, ink, true).apply {
            setLineSpacing(dp(0).toFloat(), 1.02f)
        })
        column.addView(space(12))
        column.addView(text(
            t("Настоящие растения в реальной теплице.\nУправляй своим и следи за ростом."),
            12f, secondary, false
        ).apply { setLineSpacing(dp(3).toFloat(), 1f) })
        column.addView(space(14))
        column.addView(makeVideoPreview(), LinearLayout.LayoutParams(-1, dp(224)))
        column.addView(space(11))
        column.addView(makeUpcomingCard())
        column.addView(space(10))
        column.addView(makeWatchButton(), LinearLayout.LayoutParams(-1, dp(43)))
        rootView = scroll
        return scroll
    }

    fun release() {
        movie?.stopPlayback()
        movie = null
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

        val video = VideoView(activity).apply {
            visibility = View.GONE
            setBackgroundColor(Color.TRANSPARENT)
        }
        movie = video
        frame.addView(video, FrameLayout.LayoutParams(-1, -1))

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

        val foot = LinearLayout(activity).apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(5), dp(12), dp(8))
            setBackgroundColor(color("#1E4430"))
            addView(ImageView(activity).apply {
                setImageResource(R.drawable.ic_video_outline)
                imageTintList = ColorStateList.valueOf(color("#B7D9BB"))
            }, LinearLayout.LayoutParams(dp(15), dp(15)))
            addView(text(t("Реальное видео роста растений"), 10f, color("#B8D8B8"), false)
                .apply { setPadding(dp(7), 0, 0, 0) })
        }
        frame.addView(foot, FrameLayout.LayoutParams(-1, -2, Gravity.BOTTOM))

        // VideoView attempts each source in priority order: previous full battle,
        // then individual plant timelapses. Server may return 404 for unfinished files.
        var choiceIndex = 0
        lateinit var playNext: () -> Unit
        playNext = {
            if (choiceIndex >= choices.size || activity.isFinishing || activity.isDestroyed) {
                video.visibility = View.GONE
                poster.visibility = View.VISIBLE
                play.visibility = View.VISIBLE
            } else {
                val address = api.absolute(choices[choiceIndex++].path)
                if (address != null) {
                    video.setVideoURI(Uri.parse(address))
                    video.requestFocus()
                } else {
                    playNext()
                }
            }
        }
        video.setOnPreparedListener { media ->
            media.isLooping = true
            media.setVolume(0f, 0f)
            poster.visibility = View.GONE
            video.visibility = View.VISIBLE
            play.visibility = View.GONE
            video.start()
        }
        video.setOnErrorListener { _, _, _ ->
            video.post { playNext() }
            true
        }
        video.setOnClickListener {
            if (video.isPlaying) {
                video.pause()
                play.visibility = View.VISIBLE
            } else {
                video.start()
                play.visibility = View.GONE
            }
        }
        play.setOnClickListener {
            if (video.visibility == View.VISIBLE) {
                video.start()
                play.visibility = View.GONE
            } else if (choices.isNotEmpty()) {
                choiceIndex = 0
                playNext()
            }
        }
        if (choices.isNotEmpty()) video.post { playNext() }
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
