package farm.kisamore.battle

import android.app.Activity
import android.app.Dialog
import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.widget.FrameLayout
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Immersive native onboarding, no external images/network and no simulated
 * greenhouse commands. The first-run choice is stable across APK updates.
 */
internal object BattleOnboarding {
    private const val PREF = "kisamore_battle_onboarding"
    private const val DONE = "walkthrough_v2_finished"
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
            Page("Начало и вкладки", "Как перейти к просмотру или участию:",
                listOf(
                    Tip("Присоединиться к битве", "Открывает участие в ближайшей битве. Вход и подтверждение списания Kisa потребуются до бронирования места."),
                    Tip("Смотреть битвы без входа", "Открывает битвы для зрителя без регистрации. Управлять чужим растением нельзя."),
                    Tip("Нижнее меню", "«Начало» — будущие битвы; «Битва» — фото и участники; «Профиль» — аккаунт. «История» доступна после входа, а у активного игрока «Начало» скрыто.")
                )),
            Page("Битва: фото и камеры", "Эти кнопки расположены вокруг фото полки:",
                listOf(
                    Tip("К1 / К2 слева", "Переключают камеры полки. Зелёным выделена выбранная камера."),
                    Tip("24 ч / 3 дня / Всё справа", "Запускают таймлапс за выбранный период и с текущей камеры. Крестик возвращает фотографию."),
                    Tip("Название битвы сверху", "Позволяет выбрать другую битву. Значок кубка показывает битву, в которой вы участвуете."),
                    Tip("Фото полки", "Нажмите для просмотра крупно. Тонкая зелёная рамка отмечает ваш контейнер.")
                )),
            Page("Просмотр фотографии", "Откройте фото полки и попробуйте:",
                listOf(
                    Tip("− / По размеру / +", "Уменьшить фото, сбросить масштаб или увеличить. Также можно раздвигать пальцы и дважды нажимать."),
                    Tip("Фото / ▶ 24 ч / ▶ 3 дня / ▶ Всё", "Переключают фотографию и доступные таймлапсы выбранной камеры прямо в просмотрщике."),
                    Tip("↗ Поделиться / ✕", "Отправляет фотографию через меню Android или закрывает просмотрщик.")
                )),
            Page("Мои ресурсы", "Появляются только у игрока со своим контейнером:",
                listOf(
                    Tip("Остаток / лимит", "Числа в мл и минутах показывают, сколько ресурса осталось из общего запаса."),
                    Tip("Полить", "Нажмите, выберите объём воды в мл и подтвердите команду кнопкой «Отправить»."),
                    Tip("Добавить", "Так же укажите количество питательного раствора в мл."),
                    Tip("Использовать", "Укажите минуты укрытия от света. Все эти кнопки отправляют настоящие команды только после подтверждения.")
                )),
            Page("Действия и участники", "Ниже фотографии есть ещё несколько полезных блоков:",
                listOf(
                    Tip("Последние действия / Все ›", "Показывают историю ваших команд и их статус. «Все» открывает полный журнал."),
                    Tip("Активность: 24 ч / 3 дня / 7 дней", "Меняет период графика действий, а не длительность таймлапса."),
                    Tip("Занять место", "Зритель увидит эту кнопку, пока открыт набор. При участии потребуется подтверждение стоимости в Kisa."),
                    Tip("Участники", "Нажмите на участника, чтобы выбрать его в своём прогнозе победителя. Для прогноза нужен вход.")
                )),
            Page("Профиль и история", "Где найти сообщения, настройки и диплом:",
                listOf(
                    Tip("Профиль", "Здесь показаны ваш баланс Kisa, награды, сообщения и настройки уведомлений, языка и темы."),
                    Tip("История", "После входа показывает завершённые битвы, фото, таймлапсы и цифровой диплом с QR-кодом."),
                    Tip("Оценить / Пригласить друга", "Первая кнопка открывает Google Play, вторая — отправку ссылки на приложение."),
                    Tip("Помощь", "Через «Помощь» можно повторить обучение или написать команде KisaMore.")
                ))
        )
        var selectedPage = 0
        var movePage: (Int) -> Unit = {}
        val swipeLayer = OnboardingSwipeFrame(activity) { delta -> movePage(delta) }
        val screen = LinearLayout(activity).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.rgb(7, 20, 15))
        }
        val dialog = Dialog(activity, android.R.style.Theme_Material_NoActionBar)
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE)
        swipeLayer.addView(screen, FrameLayout.LayoutParams(-1, -1))
        dialog.setContentView(swipeLayer)
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

        // The six illustrated pages are fixed-height: no vertical scrolling.
        // Artwork shrinks first; text scales gently only for very small phones
        // and long translations. The footer remains fixed and always visible.
        fun page(index: Int) {
            if (closed || activity.isFinishing || activity.isDestroyed) return
            selectedPage = index
            screen.removeAllViews()
            val ink = Color.rgb(242, 248, 239)
            val muted = Color.rgb(164, 188, 171)
            val green = Color.rgb(129, 220, 157)
            val horizontal = activity.dp(17f)
            val compact = activity.resources.configuration.screenHeightDp < 660
            val header = LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(horizontal, activity.dp(if (compact) 5f else 11f),
                    horizontal, activity.dp(2f))
            }
            header.addView(text("KisaMore", 17f, green, true).apply {
                gravity = Gravity.START or Gravity.CENTER_VERTICAL
            }, LinearLayout.LayoutParams(0, activity.dp(35f), 1f))
            header.addView(text("Пропустить обучение", 12f, muted).apply {
                gravity = Gravity.CENTER
                setPadding(activity.dp(5f), 0, activity.dp(5f), 0)
                isClickable = true
                isFocusable = true
                setOnClickListener { finish() }
            }, LinearLayout.LayoutParams(-2, activity.dp(40f)))
            screen.addView(header, LinearLayout.LayoutParams(-1, -2))

            val body = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
                setPadding(horizontal, 0, horizontal, 0)
                clipChildren = false
            }
            screen.addView(body, LinearLayout.LayoutParams(-1, 0, 1f))

            val titleSp = if (compact) 19f else 21f
            val descSp = if (compact) 11.6f else 12.4f
            val headingSp = if (compact) 11.8f else 12.5f
            val explanationSp = if (compact) 10.5f else 11.2f
            val scalable = mutableListOf<Pair<TextView, Float>>()

            val art = BattleOnboardingArtwork(activity, index)
            val initialArt = when {
                activity.resources.configuration.screenHeightDp < 570 -> 48f
                compact -> 65f
                else -> 94f
            }
            body.addView(art, LinearLayout.LayoutParams(-1, activity.dp(initialArt)))

            fun copy(value: String, size: Float, color: Int, strong: Boolean = false): TextView =
                text(value, size, color, strong).also { scalable.add(it to size) }

            body.addView(copy(pages[index].title, titleSp, ink, true).apply {
                setPadding(0, activity.dp(5f), 0, 0)
                maxLines = 2
            }, LinearLayout.LayoutParams(-1, -2))
            body.addView(copy(pages[index].description, descSp, muted).apply {
                setPadding(0, activity.dp(2f), 0, activity.dp(5f))
            }, LinearLayout.LayoutParams(-1, -2))

            val cards = mutableListOf<LinearLayout>()
            pages[index].tips.forEachIndexed { tipIndex, tip ->
                val card = LinearLayout(activity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = Gravity.CENTER_VERTICAL
                    setPadding(activity.dp(8f), activity.dp(4f),
                        activity.dp(8f), activity.dp(4f))
                    background = rounded(Color.rgb(24, 55, 39), 10f)
                }
                card.addView(copy("%02d".format(tipIndex + 1),
                    11f, green, true), LinearLayout.LayoutParams(activity.dp(25f), -2))
                val info = LinearLayout(activity).apply {
                    orientation = LinearLayout.VERTICAL
                }
                info.addView(copy(tip.control, headingSp, ink, true).apply {
                    gravity = Gravity.START
                })
                info.addView(copy(tip.explanation, explanationSp, muted).apply {
                    gravity = Gravity.START
                    setPadding(0, activity.dp(1f), 0, 0)
                })
                card.addView(info, LinearLayout.LayoutParams(0, -2, 1f))
                cards.add(card)
                body.addView(card, LinearLayout.LayoutParams(-1, -2).apply {
                    bottomMargin = activity.dp(4f)
                })
            }

            // After Android lays out the translated text, free space is checked
            // against the ACTUAL body height (not just the screen size).
            // We do not truncate instructions or allow off-screen cards.
            fun fitContent(round: Int) {
                body.post {
                    if (body.parent !== screen || selectedPage != index || round > 4) return@post
                    val last = body.getChildAt(body.childCount - 1) ?: return@post
                    val excess = last.bottom + body.paddingBottom - body.height
                    if (excess <= activity.dp(2f)) return@post
                    when (round) {
                        0 -> {
                            val params = art.layoutParams
                            params.height = (params.height - excess - activity.dp(4f))
                                .coerceAtLeast(activity.dp(24f))
                            art.layoutParams = params
                        }
                        1, 2 -> {
                            val factor = if (round == 1) .88f else .76f
                            scalable.forEach { (label, original) ->
                                label.setTextSize(TypedValue.COMPLEX_UNIT_SP,
                                    (original * factor).coerceAtLeast(9.0f))
                            }
                            cards.forEach { card ->
                                card.setPadding(activity.dp(6f), activity.dp(2f),
                                    activity.dp(6f), activity.dp(2f))
                                (card.layoutParams as LinearLayout.LayoutParams)
                                    .bottomMargin = activity.dp(2f)
                            }
                        }
                        3 -> art.visibility = View.GONE
                        4 -> {
                            scalable.forEach { (label, original) ->
                                label.setTextSize(TypedValue.COMPLEX_UNIT_SP,
                                    (original * .69f).coerceAtLeast(8.6f))
                            }
                        }
                    }
                    body.requestLayout()
                    fitContent(round + 1)
                }
            }
            fitContent(0)

            val footer = LinearLayout(activity).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(horizontal, activity.dp(4f), horizontal,
                    activity.dp(if (compact) 7f else 11f))
            }
            val dots = LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER
            }
            repeat(pages.size) { i ->
                dots.addView(View(activity).apply {
                    background = rounded(
                        if (i == index) green else Color.rgb(58, 87, 67), 5f
                    )
                    contentDescription = "${i + 1}/${pages.size}"
                    isClickable = true
                    setOnClickListener { if (i != selectedPage) page(i) }
                }, LinearLayout.LayoutParams(activity.dp(if (i == index) 26f else 7f),
                    activity.dp(6f)).apply {
                    leftMargin = activity.dp(4f); rightMargin = activity.dp(4f)
                })
            }
            footer.addView(dots, LinearLayout.LayoutParams(-1, activity.dp(16f)))
            val nav = LinearLayout(activity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val back = Button(activity).apply {
                isAllCaps = false
                text = language.t("Назад")
                textSize = 14f
                setTextColor(ink)
                background = rounded(Color.rgb(29, 64, 45), 12f)
                isEnabled = index > 0
                alpha = if (isEnabled) 1f else .32f
                setOnClickListener { if (selectedPage > 0) page(selectedPage - 1) }
            }
            nav.addView(back, LinearLayout.LayoutParams(0, activity.dp(43f), 1f).apply {
                rightMargin = activity.dp(7f)
            })
            val next = Button(activity).apply {
                isAllCaps = false
                text = language.t(if (index == pages.lastIndex) "Начать" else "Далее")
                textSize = 14f
                setTextColor(Color.rgb(5, 36, 22))
                background = rounded(green, 12f)
                stateListAnimator = null
                contentDescription = text.toString()
                setOnClickListener {
                    if (selectedPage == pages.lastIndex) finish()
                    else page(selectedPage + 1)
                }
            }
            nav.addView(next, LinearLayout.LayoutParams(0, activity.dp(43f), 1.5f))
            footer.addView(nav)
            screen.addView(footer, LinearLayout.LayoutParams(-1, -2))
        }
        movePage = { delta ->
            val target = selectedPage + delta
            if (target in pages.indices) page(target)
        }
        // Hardware/software Android Back navigates a step before leaving.
        dialog.setOnKeyListener { _, code, event ->
            if (code != KeyEvent.KEYCODE_BACK) false else {
                if (event.action == KeyEvent.ACTION_UP) {
                    if (selectedPage > 0) page(selectedPage - 1) else finish()
                }
                true
            }
        }
        page(0)
        dialog.show()
        dialog.window?.setLayout(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
    }

    private data class Tip(val control: String, val explanation: String)
    private data class Page(val title: String, val description: String, val tips: List<Tip>)
}

private fun Context.dp(value: Float): Int = (resources.displayMetrics.density * value + 0.5f).toInt()

/** Horizontal gestures work even when a TextView consumes the initial down event. */
internal fun onboardingSwipeDelta(dx: Float, dy: Float, threshold: Float): Int {
    return when {
        kotlin.math.abs(dx) < threshold -> 0
        kotlin.math.abs(dx) < kotlin.math.abs(dy) * 1.35f -> 0
        dx < 0f -> 1
        else -> -1
    }
}

internal class OnboardingSwipeFrame(
    context: Context,
    private val onNavigate: (Int) -> Unit
) : FrameLayout(context) {
    private var startX = 0f
    private var startY = 0f
    private var tracking = false
    private val threshold = context.dp(60f).toFloat()

    init { isClickable = true }

    override fun onInterceptTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                startX = event.x
                startY = event.y
                tracking = false
            }
            MotionEvent.ACTION_MOVE -> {
                if (onboardingSwipeDelta(event.x - startX,
                        event.y - startY, threshold) != 0) {
                    tracking = true
                    return true
                }
            }
        }
        return super.onInterceptTouchEvent(event)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (event.actionMasked == MotionEvent.ACTION_UP) {
            if (tracking) {
                val direction = onboardingSwipeDelta(
                    event.x - startX, event.y - startY, threshold)
                if (direction != 0) onNavigate(direction)
            }
            tracking = false
        }
        if (event.actionMasked == MotionEvent.ACTION_CANCEL) tracking = false
        return true
    }
}
