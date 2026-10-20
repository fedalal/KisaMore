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
                setFillViewport(true)
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
                activity.resources.configuration.screenHeightDp < 650 -> 178f
                activity.resources.configuration.screenHeightDp < 780 -> 220f
                else -> 252f
            }
            body.addView(BattleOnboardingArtwork(activity, index),
                LinearLayout.LayoutParams(-1, activity.dp(artHeight)))
            body.addView(text(pages[index].title, 26f, ink, true).apply {
                setPadding(activity.dp(3f), activity.dp(16f),
                    activity.dp(3f), activity.dp(5f))
                maxLines = 3
            }, LinearLayout.LayoutParams(-1, -2))
            body.addView(text(pages[index].description, 14f, muted).apply {
                setPadding(activity.dp(5f), activity.dp(4f), activity.dp(5f),
                    activity.dp(12f))
            }, LinearLayout.LayoutParams(-1, -2))

            pages[index].tips.forEachIndexed { tipIndex, tip ->
                val card = LinearLayout(activity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    gravity = Gravity.CENTER_VERTICAL
                    setPadding(activity.dp(10f), activity.dp(9f),
                        activity.dp(10f), activity.dp(9f))
                    background = rounded(Color.rgb(24, 55, 39), 14f)
                }
                val number = text("%02d".format(tipIndex + 1), 13f, green, true)
                card.addView(number, LinearLayout.LayoutParams(activity.dp(33f), -2))
                val copy = LinearLayout(activity).apply {
                    orientation = LinearLayout.VERTICAL
                }
                copy.addView(text(tip.control, 14f, ink, true).apply {
                    gravity = Gravity.START
                })
                copy.addView(text(tip.explanation, 12.5f, muted).apply {
                    gravity = Gravity.START
                    setLineSpacing(activity.dp(2f).toFloat(), 1f)
                    setPadding(0, activity.dp(3f), 0, 0)
                })
                card.addView(copy, LinearLayout.LayoutParams(0, -2, 1f))
                body.addView(card, LinearLayout.LayoutParams(-1, -2).apply {
                    bottomMargin = activity.dp(7f)
                })
            }

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

    private data class Tip(val control: String, val explanation: String)
    private data class Page(val title: String, val description: String, val tips: List<Tip>)
}

private fun Context.dp(value: Float): Int = (resources.displayMetrics.density * value + 0.5f).toInt()
