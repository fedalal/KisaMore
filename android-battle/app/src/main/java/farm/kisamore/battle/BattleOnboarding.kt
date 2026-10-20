package farm.kisamore.battle

import android.app.Activity
import android.app.Dialog
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * Immersive native onboarding, no external images/network and no simulated
 * greenhouse commands. The first-run choice is stable across APK updates.
 */
internal object BattleOnboarding {
    private const val PREF = "kisamore_battle_onboarding"
    private const val DONE = "walkthrough_v1_finished"
    private var showing = false

    fun shouldShow(context: Context): Boolean =
        !context.getSharedPreferences(PREF, Context.MODE_PRIVATE).getBoolean(DONE, false)

    fun markFinished(context: Context) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
            .putBoolean(DONE, true).apply()
    }

    fun isShowing(): Boolean = showing

    fun showIfNeeded(activity: Activity, onFinished: () -> Unit = {}): Boolean {
        if (showing) return true
        if (!shouldShow(activity)) return false
        show(activity, onFinished)
        return true
    }

    /** Replay via Profile → Help; it does not reset the completed preference. */
    fun show(activity: Activity, onFinished: () -> Unit = {}) {
        if (showing || activity.isFinishing || activity.isDestroyed) return
        showing = true
        val language = AppLanguage(activity)
        val pages = listOf(
            Page("Вы выращиваете настоящее растение",
                "Растения растут в реальной теплице. Наблюдайте за битвами или станьте участником соревнования.",
                listOf("Настоящая теплица", "6 участников", "Живой рост")),
            Page("Следите за ростом вживую",
                "Переключайте камеры, открывайте фото на весь экран и смотрите таймлапсы роста.",
                listOf("Фото полки", "Несколько камер", "Таймлапсы")),
            Page("Ресурсы ограничены — стратегия важна",
                "У игроков есть вода, питание и время укрытия от света. Каждое решение влияет на настоящее растение.",
                listOf("Вода", "Питание", "Укрытие")),
            Page("Побеждайте и получайте награды",
                "Следите за результатами. Все участники получают цифровой диплом, а победитель — награду Kisa.",
                listOf("Диплом", "Награда Kisa", "История битв"))
        )
        val screen = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(7, 20, 15))
        }
        val dialog = Dialog(activity, android.R.style.Theme_Material_NoActionBar)
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE)
        dialog.setContentView(screen)
        dialog.window?.apply {
            setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            statusBarColor = Color.rgb(7, 20, 15)
            navigationBarColor = Color.rgb(7, 20, 15)
        }
        var closed = false
        fun finish() {
            if (closed) return
            closed = true
            showing = false
            markFinished(activity)
            dialog.dismiss()
            onFinished()
        }
        dialog.setOnCancelListener { finish() }

        fun text(value: String, sp: Float, color: Int, bold: Boolean = false) =
            TextView(activity).apply {
                text = language.t(value)
                textSize = sp
                includeFontPadding = false
                setTextColor(color)
                if (bold) setTypeface(typeface, Typeface.BOLD)
                gravity = Gravity.CENTER
            }

        fun rounded(fill: Int, radius: Float) = GradientDrawable().apply {
            setColor(fill)
            cornerRadius = activity.dp(radius).toFloat()
        }

        // All text remains available on small screens: artwork/content scroll,
        // while navigation buttons remain fixed and easy to reach.
        fun page(index: Int) {
            if (closed || activity.isFinishing || activity.isDestroyed) return
            screen.removeAllViews()
            val ink = Color.rgb(242, 248, 239)
            val muted = Color.rgb(164, 188, 171)
            val green = Color.rgb(129, 220, 157)
            val horizontal = activity.dp(23f)
            val header = LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(horizontal, activity.dp(24f), horizontal, activity.dp(8f))
            }
            header.addView(text("KisaMore", 19f, green, true).apply {
                gravity = Gravity.START
                letterSpacing = 0.03f
            }, LinearLayout.LayoutParams(0, activity.dp(42f), 1f))
            val skip = text("Пропустить обучение", 13f, muted).apply {
                gravity = Gravity.CENTER
                setPadding(activity.dp(9f), 0, activity.dp(9f), 0)
                isClickable = true
                isFocusable = true
                setOnClickListener { finish() }
            }
            header.addView(skip, LinearLayout.LayoutParams(-2, activity.dp(44f)))
            screen.addView(header)

            val scroll = ScrollView(activity).apply {
                fillViewport = true
                isVerticalScrollBarEnabled = false
                clipToPadding = false
            }
            val body = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER_HORIZONTAL
                setPadding(horizontal, activity.dp(8f), horizontal, activity.dp(10f))
            }
            scroll.addView(body)
            screen.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))

            val artHeight = when {
                activity.resources.configuration.screenHeightDp < 650 -> 214f
                activity.resources.configuration.screenHeightDp < 760 -> 265f
                else -> 317f
            }
            body.addView(BattleOnboardingArtwork(activity, index),
                LinearLayout.LayoutParams(-1, activity.dp(artHeight)))
            body.addView(text(pages[index].title, 27f, ink, true).apply {
                setPadding(activity.dp(3f), activity.dp(24f),
                    activity.dp(3f), activity.dp(6f))
                maxLines = 3
            }, LinearLayout.LayoutParams(-1, -2))
            body.addView(text(pages[index].description, 15f, muted).apply {
                setLineSpacing(activity.dp(4f).toFloat(), 1f)
                setPadding(activity.dp(5f), activity.dp(7f), activity.dp(5f), 0)
                maxLines = 5
            }, LinearLayout.LayoutParams(-1, -2))

            val chipRow = LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER
                setPadding(0, activity.dp(21f), 0, 0)
            }
            pages[index].chips.forEachIndexed { chipIndex, caption ->
                val label = text(caption, 11f, if (chipIndex == 0) green else ink).apply {
                    setPadding(activity.dp(5f), 0, activity.dp(5f), 0)
                    maxLines = 2
                    minHeight = activity.dp(38f)
                    background = rounded(Color.rgb(24, 55, 39), 10f)
                }
                chipRow.addView(label, LinearLayout.LayoutParams(0, -2, 1f).apply {
                    if (chipIndex > 0) leftMargin = activity.dp(6f)
                })
            }
            body.addView(chipRow, LinearLayout.LayoutParams(-1, -2))

            val footer = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(horizontal, activity.dp(12f),
                    horizontal, activity.dp(18f))
            }
            val dots = LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER
            }
            repeat(pages.size) { dotIndex ->
                dots.addView(View(activity).apply {
                    background = rounded(
                        if (dotIndex == index) green else Color.rgb(58, 87, 67),
                        6f
                    )
                    contentDescription = "${dotIndex + 1}/${pages.size}"
                }, LinearLayout.LayoutParams(
                    activity.dp(if (dotIndex == index) 32f else 8f), activity.dp(7f)
                ).apply {
                    leftMargin = activity.dp(4f); rightMargin = activity.dp(4f)
                })
            }
            footer.addView(dots, LinearLayout.LayoutParams(-1, activity.dp(22f)))
            val next = Button(activity).apply {
                isAllCaps = false
                text = language.t(if (index == pages.lastIndex) "Начать" else "Далее")
                textSize = 16f
                setTextColor(Color.rgb(5, 36, 22))
                background = rounded(green, 16f)
                elevation = activity.dp(2f).toFloat()
                stateListAnimator = null
                contentDescription = text.toString()
                setOnClickListener {
                    if (index == pages.lastIndex) finish() else page(index + 1)
                }
            }
            footer.addView(next, LinearLayout.LayoutParams(-1, activity.dp(54f)).apply {
                topMargin = activity.dp(10f)
            })
            screen.addView(footer)
        }
        page(0)
        dialog.show()
        dialog.window?.setLayout(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
    }

    private data class Page(val title: String, val description: String, val chips: List<String>)
}

private fun Context.dp(value: Float): Int = (resources.displayMetrics.density * value + 0.5f).toInt()
