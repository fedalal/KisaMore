package farm.kisamore.battle

import android.app.Activity
import android.app.AlertDialog
import android.content.res.ColorStateList
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.Space
import android.widget.TextView
import android.widget.Toast
import java.time.OffsetDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.max

class MainActivity : Activity() {
    private lateinit var api: ApiClient
    private lateinit var game: GameStore
    private lateinit var language: AppLanguage
    private lateinit var contentHost: FrameLayout
    private lateinit var navBar: LinearLayout

    private var publicBattles: List<Battle> = emptyList()
    private var myBattles: List<Battle> = emptyList()
    private var currentScreen = "home"
    private var currentBattleId: String? = null
    private var watchBattleIndex = 0
    private var arenaFilter = "live"
    private var battleViewMode = "owner"

    private val handler = Handler(Looper.getMainLooper())
    private val autoRefresh = object : Runnable {
        override fun run() {
            val battleId = currentBattleId
            if (currentScreen == "battle" && battleId != null) {
                refreshBattle(battleId, silent = true)
                handler.postDelayed(this, 60_000)
            }
        }
    }

    private val bg = Color.parseColor("#07140F")
    private val surface = Color.parseColor("#10251C")
    private val surface2 = Color.parseColor("#173326")
    private val green = Color.parseColor("#5DD39E")
    private val gold = Color.parseColor("#FFC857")
    private val muted = Color.parseColor("#9AB3A7")
    private val danger = Color.parseColor("#FF7A7A")
    private val white = Color.WHITE

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        language = AppLanguage(applicationContext)
        api = ApiClient(applicationContext)
        game = GameStore(applicationContext)
        game.openToday()
        buildShell()
        loadAll("home")
    }

    override fun onDestroy() {
        handler.removeCallbacks(autoRefresh)
        super.onDestroy()
    }

    private fun buildShell() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(bg)
        }

        contentHost = FrameLayout(this).apply {
            setBackgroundColor(bg)
        }
        root.addView(
            contentHost,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        navBar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(6), dp(6), dp(6), dp(8))
            setBackgroundColor(surface)
        }

        navBar.addView(navButton("🏠", t("Главная")) {
            stopAutoRefresh()
            currentScreen = "home"
            showHome()
        })
        navBar.addView(navButton("🌱", t("Моё растение")) {
            stopAutoRefresh()
            val battle = activeMyBattle()
            if (battle == null) {
                if (api.hasSession()) showNoBattle() else showLogin()
            } else {
                openBattle(battle, spectator = false)
            }
        })
        navBar.addView(navButton("👁", t("Арена")) {
            stopAutoRefresh()
            currentScreen = "watch"
            showWatch()
        })
        navBar.addView(navButton("🏅", t("Профиль")) {
            stopAutoRefresh()
            currentScreen = "profile"
            showProfile()
        })

        root.addView(
            navBar,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        )

        // Android 15/16 draws modern apps edge-to-edge. Respect the real
        // status bar/cutout and navigation insets, then leave a small visual
        // gap above the app header so it never touches the system icons.
        root.setOnApplyWindowInsetsListener { view, insets ->
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val safe = insets.getInsets(
                    WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout()
                )
                view.setPadding(
                    safe.left,
                    safe.top + dp(10),
                    safe.right,
                    safe.bottom
                )
            } else {
                @Suppress("DEPRECATION")
                view.setPadding(
                    insets.systemWindowInsetLeft,
                    insets.systemWindowInsetTop + dp(10),
                    insets.systemWindowInsetRight,
                    insets.systemWindowInsetBottom
                )
            }
            insets
        }

        setContentView(root)
        root.requestApplyInsets()
    }

    private fun navButton(icon: String, label: String, action: () -> Unit): View {
        return TextView(this).apply {
            text = icon + "\n" + label
            gravity = Gravity.CENTER
            setTextColor(white)
            textSize = 11f
            setPadding(dp(4), dp(4), dp(4), dp(4))
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(0, dp(52), 1f)
        }
    }

    private fun loadAll(target: String) {
        currentScreen = target
        showLoading(t("Подключаемся к теплице…"))
        async(
            work = {
                val pub = api.publicBattles()
                val mine = if (api.hasSession()) {
                    try {
                        api.myBattles()
                    } catch (e: ApiException) {
                        if (e.statusCode == 401) emptyList() else throw e
                    }
                } else emptyList()
                Pair(pub, mine)
            },
            success = {
                publicBattles = it.first
                myBattles = it.second
                when (target) {
                    "watch" -> showWatch()
                    "profile" -> showProfile()
                    else -> showHome()
                }
            }
        )
    }

    private fun showHome() {
        currentScreen = "home"
        currentBattleId = null

        val body = compactScreen()
        body.addView(compactHeader("KISAMORE BATTLE", t("Настоящее растение. Ваши решения.")))

        val profile = game.profile()
        body.addView(
            compactStatStrip(
                t("УРОВЕНЬ ") + profile.level,
                profile.xp.toString() + " XP",
                "🔥 " + profile.streak + t(" дн.")
            )
        )

        val active = activeMyBattle()
        if (active != null) {
            body.addView(
                compactBattlePanel(
                    active,
                    label = t("МОЁ РАСТЕНИЕ"),
                    actionLabel = t("ОТКРЫТЬ МОЁ РАСТЕНИЕ")
                ) { openBattle(active, spectator = false) },
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    0,
                    1f
                ).apply { setMargins(dp(12), dp(8), dp(12), dp(6)) }
            )
        } else {
            val panel = compactCard().apply {
                gravity = Gravity.CENTER_VERTICAL
                addView(bigText(
                    if (api.hasSession()) t("Выберите следующую битву 🌱")
                    else t("Станьте игроком 🌱"),
                    19f
                ))
                addView(smallText(
                    if (api.hasSession()) t("У вас нет активной битвы")
                    else t("Войдите, чтобы управлять растением")
                ))
                addView(compactPrimaryButton(
                    if (api.hasSession()) t("СМОТРЕТЬ БИТВЫ") else t("ВОЙТИ")
                ) {
                    if (api.hasSession()) showWatch() else showLogin()
                })
            }
            body.addView(
                panel,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    0,
                    1f
                ).apply { setMargins(dp(12), dp(8), dp(12), dp(6)) }
            )
        }

        val done = profile.missions.count { it.completed }
        val mission = compactCard().apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(TextView(this@MainActivity).apply {
                text = "✓"
                textSize = 24f
                setTextColor(if (done == profile.missions.size && profile.missions.isNotEmpty()) green else gold)
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(dp(42), dp(42)))
            val copy = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(TextView(this@MainActivity).apply {
                    text = t("ЗАДАНИЯ НА СЕГОДНЯ")
                    setTextColor(white)
                    textSize = 13f
                    setTypeface(typeface, Typeface.BOLD)
                })
                addView(TextView(this@MainActivity).apply {
                    text = done.toString() + "/" + profile.missions.size + t(" заданий") +
                        " · " + profile.missions.filterNot { it.completed }.sumOf { it.reward } + " XP"
                    setTextColor(muted)
                    textSize = 12f
                })
            }
            addView(copy, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            addView(TextView(this@MainActivity).apply {
                text = "›"
                textSize = 26f
                setTextColor(muted)
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(dp(30), dp(42)))
            setOnClickListener { showMissionsDialog(profile) }
        }
        body.addView(
            mission,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(dp(12), 0, dp(12), dp(10)) }
        )

        showContent(body)
    }

    private fun showWatch() {
        currentScreen = "watch"
        currentBattleId = null

        val body = compactScreen()
        body.addView(compactHeader(t("АРЕНА"), t("Наблюдайте, болейте, делайте прогнозы")))
        body.addView(arenaFilterRow())

        val battles = arenaBattles()
        if (battles.isEmpty()) {
            val empty = compactCard().apply {
                gravity = Gravity.CENTER
                addView(bigText(t("Здесь пока нет битв"), 19f))
                addView(smallText(t("Выберите другую категорию или обновите список.")))
                addView(compactPrimaryButton(t("ОБНОВИТЬ")) { loadAll("watch") })
            }
            body.addView(
                empty,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    0,
                    1f
                ).apply { setMargins(dp(12), dp(8), dp(12), dp(12)) }
            )
            showContent(body)
            return
        }

        watchBattleIndex = watchBattleIndex.coerceIn(0, battles.lastIndex)
        val battle = battles[watchBattleIndex]

        if (battles.size > 1) {
            body.addView(battlePager(battles.size))
        }

        body.addView(
            compactBattlePanel(
                battle,
                label = statusHuman(battle.status).uppercase(),
                actionLabel = t("СМОТРЕТЬ БИТВУ")
            ) { openBattle(battle, spectator = true) },
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(dp(12), dp(4), dp(12), dp(3)) }
        )

        body.addView(
            shelfPhoto(battle, compactPhotoHeight(), compact = true),
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        showContent(body)
    }

    private fun showProfile() {
        currentScreen = "profile"
        currentBattleId = null

        val body = compactScreen()
        body.addView(compactHeader(t("ПРОФИЛЬ САДОВОДА"), api.currentUser?.displayName ?: t("Гость")))

        val profile = game.profile()
        body.addView(
            compactStatStrip(
                t("Уровень ") + profile.level,
                profile.xp.toString() + " XP",
                "🔥 " + profile.streak + t(" дней")
            )
        )

        val account = compactCard().apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            val copy = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(bigText(api.currentUser?.displayName ?: t("Гость"), 17f))
                addView(smallText(api.currentUser?.email ?: t("Аккаунт не подключён")))
            }
            addView(copy, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            if (!api.hasSession()) {
                addView(compactMiniButton(t("ВОЙТИ")) { showLogin() })
            }
        }
        body.addView(
            account,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(dp(12), dp(8), dp(12), dp(6)) }
        )

        val achievements = compactCard().apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(TextView(this@MainActivity).apply {
                text = "🏅"
                textSize = 26f
            }, LinearLayout.LayoutParams(dp(42), dp(42)))
            val copy = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(TextView(this@MainActivity).apply {
                    text = t("ДОСТИЖЕНИЯ")
                    setTextColor(white)
                    textSize = 13f
                    setTypeface(typeface, Typeface.BOLD)
                })
                addView(TextView(this@MainActivity).apply {
                    text = if (profile.badges.isEmpty()) {
                        t("Первое достижение появится уже сегодня.")
                    } else {
                        profile.badges.take(2).joinToString(" · ")
                    }
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                    setTextColor(muted)
                    textSize = 12f
                })
            }
            addView(copy, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            setOnClickListener { showAchievementsDialog(profile) }
        }
        body.addView(
            achievements,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(dp(12), 0, dp(12), dp(6)) }
        )

        val actions = GridLayout(this).apply {
            columnCount = 2
            rowCount = 2
            alignmentMode = GridLayout.ALIGN_BOUNDS
            useDefaultMargins = false
            setPadding(dp(9), dp(2), dp(9), dp(2))
        }

        fun addProfileAction(index: Int, icon: String, label: String, action: () -> Unit) {
            val row = index / 2
            val column = index % 2
            val button = profileActionButton(icon, label, action)
            button.layoutParams = GridLayout.LayoutParams(
                GridLayout.spec(row, 1f),
                GridLayout.spec(column, 1f)
            ).apply {
                width = 0
                height = 0
                setMargins(dp(4), dp(4), dp(4), dp(4))
            }
            actions.addView(button)
        }

        addProfileAction(0, "🌐", AppLanguage.displayName(language.code)) { showLanguageDialog() }
        addProfileAction(1, "🔒", t("ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ")) { openPublicPage("/privacy") }
        if (api.hasSession()) {
            addProfileAction(2, "🗑", t("УДАЛИТЬ АККАУНТ И ДАННЫЕ")) { openPublicPage("/delete-account") }
            addProfileAction(3, "↪", t("ВЫЙТИ")) {
                async(
                    work = { api.logout(); true },
                    success = {
                        myBattles = emptyList()
                        showHome()
                    }
                )
            }
        } else {
            addProfileAction(2, "🌱", t("СОЗДАТЬ АККАУНТ")) { showRegister() }
            addProfileAction(3, "→", t("ВОЙТИ")) { showLogin() }
        }
        body.addView(
            actions,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        body.addView(TextView(this).apply {
            text = appVersionLabel()
            setTextColor(muted)
            textSize = 10f
            gravity = Gravity.CENTER
            setPadding(0, dp(2), 0, dp(6))
        })

        showContent(body)
    }

    private fun showLanguageDialog() {
        val options = AppLanguage.supported.map { it.second }.toTypedArray()
        val selected = AppLanguage.supported.indexOfFirst { it.first == language.code }.coerceAtLeast(0)
        AlertDialog.Builder(this)
            .setTitle(t("Выберите язык"))
            .setSingleChoiceItems(options, selected) { dialog, which ->
                val code = AppLanguage.supported[which].first
                AppLanguage.set(this, code)
                if (api.hasSession()) {
                    Thread { runCatching { api.updateLanguage(code) } }.start()
                }
                dialog.dismiss()
                recreate()
            }
            .setNegativeButton(t("Отмена"), null)
            .show()
    }

    private fun showLogin() {
        stopAutoRefresh()
        currentScreen = "login"
        currentBattleId = null

        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader(t("ВХОД В BATTLE"), t("Ваш аккаунт KisaMore")))

        val form = card()
        val email = EditText(this).apply {
            hint = "Email"
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            backgroundTintList = ColorStateList.valueOf(green)
        }
        val password = EditText(this).apply {
            hint = t("Пароль")
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            backgroundTintList = ColorStateList.valueOf(green)
        }
        form.addView(email, matchWrap())
        form.addView(password, matchWrap())
        form.addView(space(10))
        form.addView(primaryButton(t("ВОЙТИ")) {
            if (email.text.isBlank() || password.text.isBlank()) {
                toast(t("Введите email и пароль"))
            } else {
                showLoading(t("Входим в игру…"))
                async(
                    work = { api.login(email.text.toString(), password.text.toString()) },
                    success = {
                        game.openToday()
                        loadAll("home")
                    }
                )
            }
        })
        form.addView(outlineButton(t("СОЗДАТЬ АККАУНТ")) { showRegister() })
        form.addView(TextView(this).apply {
            text = appVersionLabel()
            setTextColor(muted)
            textSize = 11f
            gravity = Gravity.CENTER
            setPadding(0, dp(10), 0, 0)
        })
        body.addView(cardWithMargin(form))
        showContent(scroll)
    }

    private fun showRegister() {
        stopAutoRefresh()
        currentScreen = "register"
        currentBattleId = null

        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader(t("СОЗДАТЬ АККАУНТ"), t("Начните свою первую битву растений")))

        val form = card()
        val name = EditText(this).apply {
            hint = t("Имя")
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PERSON_NAME
            backgroundTintList = ColorStateList.valueOf(green)
        }
        val email = EditText(this).apply {
            hint = "Email"
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            backgroundTintList = ColorStateList.valueOf(green)
        }
        val password = EditText(this).apply {
            hint = t("Пароль · минимум 5 символов")
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            backgroundTintList = ColorStateList.valueOf(green)
        }
        val confirmPassword = EditText(this).apply {
            hint = t("Повторите пароль")
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            backgroundTintList = ColorStateList.valueOf(green)
        }

        form.addView(name, matchWrap())
        form.addView(email, matchWrap())
        form.addView(password, matchWrap())
        form.addView(confirmPassword, matchWrap())
        form.addView(space(8))
        form.addView(smallText(t("Создавая аккаунт, вы соглашаетесь на обработку данных, необходимую для работы KisaMore Battle.")))
        form.addView(outlineButton(t("ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ")) {
            openPublicPage("/privacy")
        })
        form.addView(primaryButton(t("СОЗДАТЬ АККАУНТ")) {
            val displayName = name.text.toString().trim()
            val emailValue = email.text.toString().trim()
            val passwordValue = password.text.toString()
            val confirmValue = confirmPassword.text.toString()

            when {
                displayName.isBlank() -> toast(t("Введите имя"))
                emailValue.isBlank() || !emailValue.contains("@") -> toast(t("Введите корректный email"))
                passwordValue.length < 5 -> toast(t("Пароль должен содержать минимум 5 символов"))
                passwordValue != confirmValue -> toast(t("Пароли не совпадают"))
                else -> {
                    showLoading(t("Создаём аккаунт…"))
                    async(
                        work = { api.register(displayName, emailValue, passwordValue, language.code) },
                        success = {
                            game.openToday()
                            loadAll("home")
                        }
                    )
                }
            }
        })
        form.addView(outlineButton(t("УЖЕ ЕСТЬ АККАУНТ — ВОЙТИ")) { showLogin() })
        form.addView(TextView(this).apply {
            text = appVersionLabel()
            setTextColor(muted)
            textSize = 11f
            gravity = Gravity.CENTER
            setPadding(0, dp(10), 0, 0)
        })

        body.addView(cardWithMargin(form))
        showContent(scroll)
    }

    private fun showNoBattle() {
        currentScreen = "mine-empty"
        currentBattleId = null
        val body = compactScreen()
        body.addView(compactHeader(t("МОЁ РАСТЕНИЕ"), t("Активного растения пока нет")))
        val panel = compactCard().apply {
            gravity = Gravity.CENTER
            addView(TextView(this@MainActivity).apply {
                text = "🌱"
                textSize = 54f
                gravity = Gravity.CENTER
            })
            addView(bigText(t("Следующая битва ждёт 🌱"), 20f).apply { gravity = Gravity.CENTER })
            addView(smallText(t("Выберите открытую битву. После покупки места здесь появятся фото растения, ресурсы и кнопки управления.")).apply {
                gravity = Gravity.CENTER
                maxLines = 3
            })
            addView(compactPrimaryButton(t("ВЫБРАТЬ БИТВУ")) { showWatch() })
        }
        body.addView(
            panel,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            ).apply { setMargins(dp(12), dp(10), dp(12), dp(12)) }
        )
        showContent(body)
    }

    private fun openBattle(battle: Battle, spectator: Boolean = false) {
        currentScreen = "battle"
        currentBattleId = battle.id
        battleViewMode = if (spectator) "spectator" else "owner"
        showLoading(if (spectator) t("Открываем арену…") else t("Открываем растение…"))
        async(
            work = {
                if (api.hasSession()) {
                    runCatching { api.authenticatedBattle(battle.id) }.getOrElse { battle }
                } else battle
            },
            success = {
                renderBattle(it)
                startAutoRefresh()
            }
        )
    }

    private fun refreshBattle(id: String, silent: Boolean) {
        val fallback = (myBattles + publicBattles).firstOrNull { it.id == id } ?: return
        if (!silent) showLoading(t("Обновляем арену…"))
        async(
            work = {
                if (api.hasSession()) {
                    runCatching { api.authenticatedBattle(id) }.getOrElse { fallback }
                } else {
                    api.publicBattles().firstOrNull { it.id == id } ?: fallback
                }
            },
            success = {
                replaceBattleInCaches(it)
                if (currentScreen == "battle" && currentBattleId == id) renderBattle(it)
            },
            failure = {
                if (!silent) showError(it)
            }
        )
    }

    private fun renderBattle(battle: Battle) {
        currentScreen = "battle"
        currentBattleId = battle.id

        val spectator = battleViewMode == "spectator"
        val body = compactScreen()
        body.addView(
            compactArenaHeader(
                battle,
                if (spectator) t("АРЕНА") else t("МОЁ РАСТЕНИЕ")
            )
        )

        body.addView(
            shelfPhoto(battle, compactPhotoHeight(), compact = true),
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        if (spectator) {
            if (battle.status == "open") {
                body.addView(compactJoinRow(battle))
            }
            body.addView(compactSpectatorActions(battle))
        } else {
            val mineEntries = battle.entries.filter { it.isMine }
            if (mineEntries.isEmpty()) {
                val message = compactCard().apply {
                    gravity = Gravity.CENTER
                    addView(smallText(t("Это растение не привязано к вашему аккаунту.")))
                    addView(compactPrimaryButton(t("ПЕРЕЙТИ В АРЕНУ")) {
                        battleViewMode = "spectator"
                        renderBattle(battle)
                    })
                }
                body.addView(
                    message,
                    LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT
                    ).apply { setMargins(dp(12), dp(4), dp(12), dp(8)) }
                )
            } else {
                // A user can own only one plant in a battle.
                val selectedMine = mineEntries.first()
                body.addView(compactResources(battle, selectedMine))
                if (battle.status == "growing") {
                    body.addView(compactCommandRow(battle, selectedMine))
                }
            }
        }

        showContent(body)
    }

    private fun arenaHeader(battle: Battle): View {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(20), dp(20), dp(16))
            background = gradientDrawable("#174B34", "#07140F")
        }
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val textBlock = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        textBlock.addView(bigText(battle.title, 27f))
        textBlock.addView(smallText(battle.plantName + t(" · полка ") + battle.rackId + " · " + dayLabel(battle)))
        row.addView(textBlock, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        row.addView(statusPill(battle.status))
        box.addView(row)
        box.addView(space(10))
        box.addView(
            statStrip(
                battle.entriesCount.toString() + "/" + battle.maxEntries + " 🌱",
                "🎯 " + battle.predictionTotal,
                "🏆 " + battle.winnerRewardKisa + " Kisa"
            )
        )
        return box
    }

    private fun shelfPhoto(
        battle: Battle,
        imageHeightDp: Int = 260,
        compact: Boolean = false
    ): View {
        val frame = FrameLayout(this).apply {
            background = rounded(surface2, if (compact) 16 else 22)
            clipToOutline = true
        }
        val image = ImageView(this).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            setBackgroundColor(surface2)
            contentDescription = t("Фото полки")
        }
        frame.addView(
            image,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(imageHeightDp)
            )
        )

        val grid = GridLayout(this).apply {
            rowCount = 3
            columnCount = 2
            setPadding(dp(4), dp(4), dp(4), dp(4))
        }
        repeat(6) { index ->
            val slot = index + 1
            val entry = battle.entries.firstOrNull { it.slotNumber == slot }
            val mine = entry?.isMine == true
            val cell = TextView(this).apply {
                text = if (mine) slot.toString() + t("  ★ ВЫ") else slot.toString()
                gravity = Gravity.TOP or Gravity.START
                setPadding(dp(7), dp(5), dp(3), dp(3))
                setTextColor(if (mine) gold else white)
                textSize = if (compact) 10f else 11f
                setTypeface(typeface, Typeface.BOLD)
            }
            val params = GridLayout.LayoutParams(
                GridLayout.spec(index / 2, 1f),
                GridLayout.spec(index % 2, 1f)
            ).apply {
                width = 0
                height = 0
            }
            grid.addView(cell, params)
        }
        frame.addView(
            grid,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(imageHeightDp)
            )
        )

        val views = if (battle.cameraViews.isNotEmpty()) {
            battle.cameraViews
        } else {
            battle.rackPhotoUrl?.let { listOf(CameraView("primary", true, it)) } ?: emptyList()
        }

        fun loadCamera(view: CameraView) {
            async(
                work = { api.loadBitmap(api.absolute(view.photoUrl)) },
                success = { bitmap -> if (bitmap != null) image.setImageBitmap(bitmap) },
                failure = { }
            )
        }

        val primaryView = views.firstOrNull { it.primary } ?: views.firstOrNull()
        if (primaryView != null) loadCamera(primaryView)

        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), if (compact) dp(4) else dp(8), dp(12), dp(2))
            addView(
                frame,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    dp(imageHeightDp)
                )
            )

            if (views.size > 1) {
                val cameraRow = LinearLayout(this@MainActivity).apply {
                    orientation = LinearLayout.HORIZONTAL
                    setPadding(0, dp(4), 0, 0)
                }
                views.forEachIndexed { index, view ->
                    cameraRow.addView(
                        compactMiniButton(
                            if (view.primary) "★ " + t("Основная") else "📷 " + (index + 1)
                        ) { loadCamera(view) },
                        LinearLayout.LayoutParams(
                            0,
                            if (compact) dp(36) else ViewGroup.LayoutParams.WRAP_CONTENT,
                            1f
                        ).apply { setMargins(dp(2), 0, dp(2), 0) }
                    )
                }
                addView(cameraRow)
            }
        }
    }

    private fun resourceCard(battle: Battle, entry: BattleEntry): View {
        val c = card()
        c.addView(bigText(t("🌱 Контейнер #") + entry.slotNumber, 19f))
        c.addView(smallText(if (battle.status == "growing") t("Вы принимаете решения") else statusHuman(battle.status)))
        c.addView(space(8))
        c.addView(resourceRow(t("💧 Вода"), battle.waterBudgetMl, entry.waterUsedMl, t("мл")))
        c.addView(resourceRow(t("🧪 Питание"), battle.nutrientBudgetMl, entry.nutrientUsedMl, t("мл")))
        c.addView(resourceRow(t("🌙 Без света"), battle.shadeBudgetMinutes, entry.shadeUsedMinutes, t("мин")))

        if (battle.status == "growing") {
            c.addView(space(8))
            c.addView(labelText(t("ВАШ ХОД"), gold))
            val actions = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
            }
            actions.addView(commandButton(t("💧\nПолить")) { amountDialog(battle, entry, "water") })
            actions.addView(commandButton(t("🧪\nПитание")) { amountDialog(battle, entry, "nutrient") })
            actions.addView(commandButton(t("🌙\nЗакрыть")) { amountDialog(battle, entry, "shade") })
            c.addView(actions)
        }

        return cardWithMargin(c)
    }

    private fun resourceRow(title: String, budget: Int, used: Int, unit: String): View {
        val remain = GameRules.remaining(budget, used)
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(5), 0, dp(7))
        }
        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
        }
        top.addView(TextView(this).apply {
            text = title
            setTextColor(white)
            textSize = 14f
            setTypeface(typeface, Typeface.BOLD)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        top.addView(TextView(this).apply {
            text = remain.toString() + " / " + budget + " " + unit
            setTextColor(muted)
            textSize = 13f
        })
        wrap.addView(top)
        wrap.addView(progress(remain, max(1, budget)))
        return wrap
    }

    private fun predictionCard(battle: Battle): View {
        val c = card()
        val ranked = battle.entries.sortedByDescending { battle.predictionCounts[it.id] ?: 0 }
        ranked.forEach { entry ->
            val votes = battle.predictionCounts[entry.id] ?: 0
            val selected = battle.myPredictionEntryId == entry.id
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, dp(4), 0, dp(4))
            }
            row.addView(TextView(this).apply {
                text = (if (selected) "🌟 " else "🌱 ") + t("Контейнер #") + entry.slotNumber
                setTextColor(if (selected) gold else white)
                textSize = 15f
                setTypeface(typeface, Typeface.BOLD)
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            row.addView(TextView(this).apply {
                text = votes.toString() + t(" голосов")
                setTextColor(muted)
                textSize = 12f
            })
            row.setOnClickListener {
                if (!api.hasSession()) {
                    showLogin()
                } else if (battle.status == "finished") {
                    toast(t("Прогнозы уже закрыты"))
                } else {
                    sendPrediction(battle, entry)
                }
            }
            c.addView(row)
        }
        c.addView(space(7))
        c.addView(smallText(t("Можно менять выбор до окончания битвы. Прогноз не влияет на растение.")))
        return cardWithMargin(c)
    }

    private fun timelapseCard(battle: Battle): View {
        val c = card()
        val preferred = battle.mine ?: battle.entries.firstOrNull()
        if (preferred == null) {
            c.addView(smallText(t("Таймлапс появится после посадки.")))
            return cardWithMargin(c)
        }
        c.addView(bigText(t("Контейнер #") + preferred.slotNumber, 18f))
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(actionButton(t("🎬 24 ЧАСА")) {
            openVideo(preferred.timelapse24hUrl)
        })
        buttons.addView(actionButton(t("🎞 3 ДНЯ")) {
            openVideo(preferred.timelapse3dUrl)
        })
        c.addView(buttons)
        return cardWithMargin(c)
    }

    private fun eventFeed(battle: Battle): View {
        val c = card()
        c.addView(eventLine("🌿", t("Битва идёт"), battle.plantName + " · " + dayLabel(battle)))
        if (battle.predictionTotal > 0) {
            c.addView(eventLine("🎯", t("Зрители спорят о победителе"), battle.predictionTotal.toString() + t(" прогнозов")))
        }
        if (battle.status == "open") {
            c.addView(eventLine("🎟", t("Набор участников"), t("Свободно мест: ") + battle.remainingEntries))
        }
        val ownActions = battle.entries.filter { it.isMine }.flatMap { entry ->
            entry.actions.take(5).map { Pair(entry, it) }
        }.sortedByDescending { it.second.requestedAt ?: "" }

        ownActions.take(8).forEach { pair ->
            val entry = pair.first
            val action = pair.second
            c.addView(
                eventLine(
                    actionIcon(action.kind),
                    t("Ваш ход · контейнер #") + entry.slotNumber,
                    actionHuman(action) + " · " + actionStatus(action.status)
                )
            )
        }
        if (ownActions.isEmpty() && battle.status == "growing") {
            c.addView(eventLine("⏳", t("Следующий ход за вами"), t("Решите, стоит ли сейчас тратить ресурсы")))
        }
        return cardWithMargin(c)
    }

    private fun sendPrediction(battle: Battle, entry: BattleEntry) {
        toast(t("Сохраняем прогноз…"))
        async(
            work = { api.predict(battle.id, entry.id) },
            success = { updated ->
                game.completeMission("predict")
                replaceBattleInCaches(updated)
                renderBattle(updated)
                toast(t("+10 XP · прогноз сохранён"))
            },
            failure = { error ->
                if (error is ApiException && error.statusCode == 404) {
                    toast(t("Для прогнозов нужно обновить Battle API на сервере"))
                } else {
                    showError(error)
                }
            }
        )
    }

    private fun amountDialog(battle: Battle, entry: BattleEntry, kind: String) {
        val input = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_NUMBER
            setTextColor(Color.BLACK)
            hint = if (kind == "shade") t("минуты") else t("мл")
        }
        val presets = when (kind) {
            "water" -> intArrayOf(30, 60, 100)
            "nutrient" -> intArrayOf(5, 10, 20)
            else -> intArrayOf(30, 60, 120)
        }
        val title = when (kind) {
            "water" -> t("💧 Полить растение")
            "nutrient" -> t("🧪 Добавить питание")
            else -> t("🌙 Закрыть от света")
        }

        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), 0, dp(22), 0)
        }
        val presetRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        presets.forEach { amount ->
            presetRow.addView(Button(this).apply {
                text = amount.toString()
                setOnClickListener { input.setText(amount.toString()) }
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        wrap.addView(presetRow)
        wrap.addView(input)

        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(t("Это реальная команда. Ресурс будет списан из лимита растения."))
            .setView(wrap)
            .setNegativeButton(t("Отмена"), null)
            .setPositiveButton(t("Отправить")) { _, _ ->
                val amount = input.text.toString().toIntOrNull() ?: 0
                if (amount <= 0) {
                    toast(t("Укажите количество"))
                } else {
                    executeCommand(battle, entry, kind, amount)
                }
            }
            .show()
    }

    private fun executeCommand(battle: Battle, entry: BattleEntry, kind: String, amount: Int) {
        showLoading(t("Передаём команду в теплицу…"))
        async(
            work = {
                api.sendAction(battle.id, entry.id, kind, amount)
                api.authenticatedBattle(battle.id)
            },
            success = { updated ->
                game.completeMission("command")
                replaceBattleInCaches(updated)
                renderBattle(updated)
                toast(t("+15 XP · команда принята"))
            }
        )
    }

    private fun confirmJoin(battle: Battle) {
        AlertDialog.Builder(this)
            .setTitle(t("Занять место в битве?"))
            .setMessage(t("Будет использована стоимость участия в Kisa. После покупки место закрепится за вашим аккаунтом."))
            .setNegativeButton(t("Отмена"), null)
            .setPositiveButton(t("Участвовать")) { _, _ ->
                showLoading(t("Бронируем растение…"))
                async(
                    work = {
                        api.joinBattle(battle.id, 1)
                        api.myBattles()
                    },
                    success = {
                        myBattles = it
                        val joined = it.firstOrNull { item -> item.id == battle.id }
                        if (joined != null) openBattle(joined) else loadAll("home")
                    }
                )
            }
            .show()
    }

    private fun openPublicPage(path: String) {
        val url = api.absolute(path) ?: return
        runCatching {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        }.onFailure {
            toast(t("Не удалось открыть страницу"))
        }
    }

    private fun openVideo(path: String?) {
        val url = api.absolute(path)
        if (url.isNullOrBlank()) {
            toast(t("Таймлапс пока не готов"))
            return
        }
        game.completeMission("video")
        runCatching {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            toast(t("+5 XP · наблюдение засчитано"))
        }.onFailure {
            toast(t("Не удалось открыть видео"))
        }
    }

    private fun battleHeroCard(battle: Battle, mine: Boolean): View {
        val c = card()
        c.addView(labelText(if (mine) t("🎮 ВЫ В ИГРЕ") else "● LIVE", if (mine) gold else green))
        c.addView(bigText(battle.title, 21f))
        c.addView(smallText(battle.plantName + " · " + dayLabel(battle)))
        c.addView(space(8))
        c.addView(statStrip(
            battle.entriesCount.toString() + "/" + battle.maxEntries,
            "🎯 " + battle.predictionTotal,
            "🏆 " + battle.winnerRewardKisa + " K"
        ))
        c.addView(primaryButton(if (mine) t("ОТКРЫТЬ МОЁ РАСТЕНИЕ") else t("СМОТРЕТЬ LIVE")) {
            openBattle(battle, spectator = !mine)
        })
        return cardWithMargin(c)
    }

    private fun battleListCard(battle: Battle): View {
        val c = card()
        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val plant = TextView(this).apply {
            text = "🌿"
            textSize = 34f
        }
        top.addView(plant)
        val names = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(10), 0, dp(8), 0)
        }
        names.addView(bigText(battle.title, 18f))
        names.addView(smallText(battle.plantName + t(" · полка ") + battle.rackId))
        top.addView(names, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        top.addView(statusPill(battle.status))
        c.addView(top)
        c.addView(space(8))
        c.addView(statStrip(
            battle.entriesCount.toString() + "/" + battle.maxEntries + " 🌱",
            "🎯 " + battle.predictionTotal,
            if (battle.status == "open") battle.remainingEntries.toString() + t(" мест") else dayLabel(battle)
        ))
        c.setOnClickListener { openBattle(battle, spectator = true) }
        return cardWithMargin(c)
    }

    private fun missionsCard(profile: GameProfile): View {
        val c = card()
        profile.missions.forEach { mission ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
                setPadding(0, dp(5), 0, dp(5))
            }
            row.addView(TextView(this).apply {
                text = mission.icon
                textSize = 22f
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(dp(38), dp(38)))
            val mid = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            mid.addView(TextView(this).apply {
                text = mission.title
                setTextColor(if (mission.completed) muted else white)
                textSize = 14f
                setTypeface(typeface, Typeface.BOLD)
            })
            mid.addView(TextView(this).apply {
                text = if (mission.completed) t("Выполнено") else "+" + mission.reward + " XP"
                setTextColor(if (mission.completed) green else gold)
                textSize = 12f
            })
            row.addView(mid, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            row.addView(TextView(this).apply {
                text = if (mission.completed) "✓" else "○"
                textSize = 23f
                setTextColor(if (mission.completed) green else muted)
            })
            c.addView(row)
        }
        val done = profile.missions.count { it.completed }
        c.addView(space(5))
        c.addView(smallText(t("Сегодня: ") + done + "/" + profile.missions.size + t(" заданий")))
        return cardWithMargin(c)
    }

    private fun eventLine(icon: String, title: String, subtitle: String): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(7), 0, dp(7))
            addView(TextView(this@MainActivity).apply {
                text = icon
                textSize = 22f
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(dp(42), dp(42)))
            val copy = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
            }
            copy.addView(TextView(this@MainActivity).apply {
                text = title
                setTextColor(white)
                textSize = 14f
                setTypeface(typeface, Typeface.BOLD)
            })
            copy.addView(TextView(this@MainActivity).apply {
                text = subtitle
                setTextColor(muted)
                textSize = 12f
            })
            addView(copy, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
    }

    private fun infoLine(icon: String, title: String, subtitle: String): View =
        eventLine(icon, title, subtitle)

    private fun actionHuman(action: BattleAction): String {
        val unit = if (action.kind == "shade") t(" мин") else t(" мл")
        return when (action.kind) {
            "water" -> t("Полив ") + action.amount + unit
            "nutrient" -> t("Питание ") + action.amount + unit
            "shade" -> t("Без света ") + action.amount + unit
            else -> action.kind + " " + action.amount
        }
    }

    private fun actionIcon(kind: String): String = when (kind) {
        "water" -> "💧"
        "nutrient" -> "🧪"
        "shade" -> "🌙"
        else -> "🎮"
    }

    private fun actionStatus(status: String): String = when (status) {
        "pending" -> t("ожидает выполнения")
        "completed" -> t("выполнено")
        "cancelled" -> t("отменено")
        else -> status
    }

    private fun activeMyBattle(): Battle? =
        myBattles.firstOrNull { it.status != "finished" } ?: myBattles.firstOrNull()

    private fun replaceBattleInCaches(updated: Battle) {
        publicBattles = publicBattles.map { if (it.id == updated.id) updated else it }
        myBattles = myBattles.map { if (it.id == updated.id) updated else it }
        if (updated.mine != null && myBattles.none { it.id == updated.id }) {
            myBattles = listOf(updated) + myBattles
        }
    }

    private fun startAutoRefresh() {
        handler.removeCallbacks(autoRefresh)
        handler.postDelayed(autoRefresh, 60_000)
    }

    private fun stopAutoRefresh() {
        handler.removeCallbacks(autoRefresh)
        currentBattleId = null
    }

    private fun showLoading(message: String) {
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(30), dp(30), dp(30), dp(30))
            setBackgroundColor(bg)
        }
        val progress = ProgressBar(this).apply {
            indeterminateTintList = ColorStateList.valueOf(green)
        }
        wrap.addView(progress, LinearLayout.LayoutParams(dp(52), dp(52)))
        wrap.addView(space(14))
        wrap.addView(TextView(this).apply {
            text = message
            setTextColor(muted)
            textSize = 14f
            gravity = Gravity.CENTER
        })
        showContent(wrap)
    }

    private fun showError(error: Throwable) {
        val message = error.message ?: t("Не удалось связаться с сервером")
        toast(message)
        if (currentScreen == "battle" && currentBattleId != null) {
            val fallback = (myBattles + publicBattles).firstOrNull { it.id == currentBattleId }
            if (fallback != null) renderBattle(fallback) else showHome()
        } else {
            showHome()
        }
    }

    private fun <T> async(
        work: () -> T,
        success: (T) -> Unit,
        failure: (Throwable) -> Unit = { showError(it) }
    ) {
        Thread {
            try {
                val result = work()
                runOnUiThread {
                    if (!isFinishing && !isDestroyed) success(result)
                }
            } catch (t: Throwable) {
                runOnUiThread {
                    if (!isFinishing && !isDestroyed) failure(t)
                }
            }
        }.start()
    }

    private fun compactScreen(): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(bg)
            setPadding(0, 0, 0, dp(2))
        }

    private fun compactHeader(title: String, subtitle: String): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(10))
            background = gradientDrawable("#174B34", "#0A1A13")
            addView(bigText(title, 21f).apply {
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
            addView(TextView(this@MainActivity).apply {
                text = subtitle
                setTextColor(muted)
                textSize = 11f
                maxLines = 1
                ellipsize = android.text.TextUtils.TruncateAt.END
            })
        }

    private fun compactCard(): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(13), dp(11), dp(13), dp(11))
            background = rounded(surface, 16)
        }

    private fun compactStatStrip(a: String, b: String, c: String): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(9), dp(7), dp(9), dp(2))
            addView(compactStatCell(a))
            addView(compactStatCell(b))
            addView(compactStatCell(c))
        }

    private fun compactStatCell(value: String): View =
        TextView(this).apply {
            text = value
            setTextColor(white)
            gravity = Gravity.CENTER
            textSize = 11f
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            setTypeface(typeface, Typeface.BOLD)
            setPadding(dp(3), dp(7), dp(3), dp(7))
            background = rounded(Color.parseColor("#18392B"), 10)
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                setMargins(dp(3), 0, dp(3), 0)
            }
        }

    private fun compactPrimaryButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 11f
            setTextColor(Color.BLACK)
            setTypeface(typeface, Typeface.BOLD)
            backgroundTintList = ColorStateList.valueOf(green)
            minHeight = 0
            minimumHeight = 0
            setPadding(dp(8), 0, dp(8), 0)
            setOnClickListener { action() }
            layoutParams = matchWrap().apply {
                height = dp(42)
                topMargin = dp(7)
            }
        }

    private fun compactMiniButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 10f
            setTextColor(white)
            backgroundTintList = ColorStateList.valueOf(surface2)
            minHeight = 0
            minimumHeight = 0
            setPadding(dp(5), 0, dp(5), 0)
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                dp(38)
            )
        }

    private fun compactBattlePanel(
        battle: Battle,
        label: String,
        actionLabel: String,
        action: () -> Unit
    ): View =
        compactCard().apply {
            addView(labelText(label, if (battle.status == "growing") green else gold))
            val row = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val copy = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(bigText(battle.title, 18f).apply {
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                })
                addView(smallText(
                    battle.plantName + t(" · полка ") + battle.rackId + " · " + dayLabel(battle)
                ).apply {
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                })
            }
            row.addView(copy, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            row.addView(statusPill(battle.status))
            addView(row)
            addView(compactStatStrip(
                battle.entriesCount.toString() + "/" + battle.maxEntries + " 🌱",
                "🎯 " + battle.predictionTotal,
                "🏆 " + battle.winnerRewardKisa + " K"
            ))
            addView(compactPrimaryButton(actionLabel, action))
        }

    private fun compactArenaHeader(battle: Battle, contextLabel: String): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), dp(8), dp(14), dp(7))
            background = gradientDrawable("#174B34", "#0A1A13")
            val copy = LinearLayout(this@MainActivity).apply {
                orientation = LinearLayout.VERTICAL
                addView(labelText(contextLabel, green))
                addView(bigText(battle.title, 18f).apply {
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                })
                addView(TextView(this@MainActivity).apply {
                    text = battle.plantName + t(" · полка ") + battle.rackId + " · " + dayLabel(battle)
                    setTextColor(muted)
                    textSize = 10f
                    maxLines = 1
                    ellipsize = android.text.TextUtils.TruncateAt.END
                })
            }
            addView(copy, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            addView(statusPill(battle.status))
        }

    private fun compactPhotoHeight(): Int {
        val density = resources.displayMetrics.density.coerceAtLeast(1f)
        val screenDp = resources.displayMetrics.heightPixels / density
        return when {
            screenDp < 650f -> 145
            screenDp < 740f -> 170
            screenDp < 860f -> 205
            else -> 230
        }
    }

    private fun compactResources(battle: Battle, entry: BattleEntry): View {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(9), dp(3), dp(9), dp(2))
        }
        row.addView(resourceMiniCell("💧", GameRules.remaining(battle.waterBudgetMl, entry.waterUsedMl).toString() + " " + t("мл")))
        row.addView(resourceMiniCell("🧪", GameRules.remaining(battle.nutrientBudgetMl, entry.nutrientUsedMl).toString() + " " + t("мл")))
        row.addView(resourceMiniCell("🌙", GameRules.remaining(battle.shadeBudgetMinutes, entry.shadeUsedMinutes).toString() + " " + t("мин")))
        return row
    }

    private fun resourceMiniCell(icon: String, value: String): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(3), dp(5), dp(3), dp(5))
            background = rounded(surface, 11)
            addView(TextView(this@MainActivity).apply {
                text = icon
                textSize = 17f
                gravity = Gravity.CENTER
            })
            addView(TextView(this@MainActivity).apply {
                text = value
                setTextColor(white)
                textSize = 10f
                setTypeface(typeface, Typeface.BOLD)
                gravity = Gravity.CENTER
            })
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                setMargins(dp(3), 0, dp(3), 0)
            }
        }

    private fun compactCommandRow(battle: Battle, entry: BattleEntry): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(9), dp(2), dp(9), dp(2))
            addView(compactActionButton("💧", t("Полить")) { amountDialog(battle, entry, "water") })
            addView(compactActionButton("🧪", t("Питание")) { amountDialog(battle, entry, "nutrient") })
            addView(compactActionButton("🌙", t("Закрыть")) { amountDialog(battle, entry, "shade") })
        }

    private fun compactActionButton(icon: String, label: String, action: () -> Unit): View =
        Button(this).apply {
            text = icon + " " + label
            textSize = 10f
            setTextColor(white)
            backgroundTintList = ColorStateList.valueOf(surface2)
            minHeight = 0
            minimumHeight = 0
            setPadding(dp(3), 0, dp(3), 0)
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(0, dp(42), 1f).apply {
                setMargins(dp(3), 0, dp(3), 0)
            }
        }


    private fun compactJoinRow(battle: Battle): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(12), dp(3), dp(12), dp(3))
            addView(TextView(this@MainActivity).apply {
                text = t("Свободно мест: ") + battle.remainingEntries
                setTextColor(white)
                textSize = 12f
                setTypeface(typeface, Typeface.BOLD)
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            addView(compactMiniButton(
                if (api.hasSession()) t("ЗАНЯТЬ МЕСТО") else t("ВОЙТИ И УЧАСТВОВАТЬ")
            ) {
                if (api.hasSession()) confirmJoin(battle) else showLogin()
            })
        }

    private fun compactSpectatorActions(battle: Battle): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(9), dp(3), dp(9), dp(6))
            addView(compactActionButton("🎯", t("Прогнозы")) {
                showBattleDialog(t("ПРОГНОЗ ЗРИТЕЛЕЙ"), predictionCard(battle))
            })
            addView(compactActionButton("🎬", t("Таймлапсы")) {
                showBattleDialog(t("ТАЙМЛАПС"), timelapseCard(battle))
            })
            addView(compactActionButton("☰", t("СОБЫТИЯ")) {
                showBattleDialog(t("СОБЫТИЯ"), eventFeed(battle))
            })
        }

    private fun arenaBattles(): List<Battle> =
        when (arenaFilter) {
            "open" -> publicBattles.filter { it.status == "open" }
            "finished" -> publicBattles.filter { it.status in listOf("finished", "cancelled") }
            else -> publicBattles.filter {
                it.status in listOf("ready_to_plant", "planting", "growing", "judging")
            }
        }

    private fun arenaFilterRow(): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(9), dp(5), dp(9), dp(2))
            addView(arenaFilterButton("live", "LIVE"))
            addView(arenaFilterButton("open", t("Набор").uppercase()))
            addView(arenaFilterButton("finished", t("ЗАВЕРШЕННЫЕ")))
        }

    private fun arenaFilterButton(filter: String, label: String): View =
        Button(this).apply {
            text = label
            textSize = 9f
            setTextColor(if (arenaFilter == filter) Color.BLACK else white)
            backgroundTintList = ColorStateList.valueOf(
                if (arenaFilter == filter) green else surface2
            )
            minHeight = 0
            minimumHeight = 0
            setPadding(dp(2), 0, dp(2), 0)
            setOnClickListener {
                if (arenaFilter != filter) {
                    arenaFilter = filter
                    watchBattleIndex = 0
                    showWatch()
                }
            }
            layoutParams = LinearLayout.LayoutParams(0, dp(34), 1f).apply {
                setMargins(dp(3), 0, dp(3), 0)
            }
        }

    private fun battlePager(count: Int): View =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(12), dp(5), dp(12), dp(1))
            addView(compactMiniButton("‹") {
                watchBattleIndex = (watchBattleIndex - 1 + count) % count
                showWatch()
            })
            addView(TextView(this@MainActivity).apply {
                text = (watchBattleIndex + 1).toString() + " / " + count
                setTextColor(muted)
                textSize = 12f
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(0, dp(38), 1f))
            addView(compactMiniButton("›") {
                watchBattleIndex = (watchBattleIndex + 1) % count
                showWatch()
            })
        }

    private fun profileActionButton(icon: String, label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = icon + "\n" + label
            textSize = 10f
            maxLines = 2
            gravity = Gravity.CENTER
            setTextColor(white)
            backgroundTintList = ColorStateList.valueOf(surface2)
            minHeight = 0
            minimumHeight = 0
            minWidth = 0
            minimumWidth = 0
            setPadding(dp(8), dp(4), dp(8), dp(4))
            setOnClickListener { action() }
        }

    private fun showBattleDialog(title: String, content: View) {
        (content.parent as? ViewGroup)?.removeView(content)
        val scroll = ScrollView(this).apply {
            setPadding(dp(6), dp(2), dp(6), dp(2))
            addView(content)
        }
        AlertDialog.Builder(this)
            .setTitle(title)
            .setView(scroll)
            .setPositiveButton("OK", null)
            .show()
    }

    private fun showMissionsDialog(profile: GameProfile) {
        showBattleDialog(t("ЗАДАНИЯ НА СЕГОДНЯ"), missionsCard(profile))
    }

    private fun showAchievementsDialog(profile: GameProfile) {
        val list = card()
        if (profile.badges.isEmpty()) {
            list.addView(smallText(t("Первое достижение появится уже сегодня.")))
        } else {
            profile.badges.forEach { list.addView(bigText(it, 16f)) }
        }
        showBattleDialog(t("ДОСТИЖЕНИЯ"), cardWithMargin(list))
    }

    private fun showContent(view: View) {
        contentHost.removeAllViews()
        contentHost.addView(
            view,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )
    }

    private fun screenScroll(): ScrollView {
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, 0, 0, dp(24))
        }
        return ScrollView(this).apply {
            setBackgroundColor(bg)
            isFillViewport = true
            addView(
                body,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
            )
        }
    }

    private fun gameHeader(title: String, subtitle: String): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(20))
            background = gradientDrawable("#174B34", "#07140F")
            addView(bigText(title, 29f))
            addView(smallText(subtitle))
        }
    }

    private fun card(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(16), dp(16), dp(16))
        background = rounded(surface, 20)
    }

    private fun cardWithMargin(view: View): View {
        return FrameLayout(this).apply {
            setPadding(dp(16), dp(4), dp(16), dp(8))
            addView(
                view,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
            )
        }
    }

    private fun sectionTitle(title: String, subtitle: String): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(21), dp(20), dp(8))
            addView(labelText(title, green))
            addView(TextView(this@MainActivity).apply {
                text = subtitle
                setTextColor(muted)
                textSize = 12f
            })
        }
    }

    private fun statStrip(a: String, b: String, c: String): View {
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            addView(statCell(a))
            addView(statCell(b))
            addView(statCell(c))
        }
    }

    private fun statCell(value: String): View {
        return TextView(this).apply {
            text = value
            setTextColor(white)
            gravity = Gravity.CENTER
            textSize = 12f
            setTypeface(typeface, Typeface.BOLD)
            setPadding(dp(4), dp(8), dp(4), dp(8))
            background = rounded(Color.parseColor("#18392B"), 12)
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                setMargins(dp(3), 0, dp(3), 0)
            }
        }
    }

    private fun statusPill(status: String): View {
        val color = if (status in listOf("growing", "open")) green else if (status == "finished") muted else gold
        return TextView(this).apply {
            text = statusHuman(status).uppercase()
            setTextColor(color)
            textSize = 9f
            setTypeface(typeface, Typeface.BOLD)
            setPadding(dp(8), dp(5), dp(8), dp(5))
            background = rounded(withAlpha(color, 45), 20)
        }
    }

    private fun statusHuman(status: String): String = when (status) {
        "open" -> t("Набор")
        "ready_to_plant" -> t("Готово к посадке")
        "planting" -> t("Посадка")
        "growing" -> "Live"
        "judging" -> t("Финал")
        "finished" -> t("Завершено")
        else -> status
    }

    private fun primaryButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            setTextColor(Color.BLACK)
            setTypeface(typeface, Typeface.BOLD)
            backgroundTintList = ColorStateList.valueOf(green)
            setOnClickListener { action() }
            layoutParams = matchWrap().apply { topMargin = dp(10) }
        }

    private fun outlineButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            setTextColor(white)
            backgroundTintList = ColorStateList.valueOf(surface2)
            setOnClickListener { action() }
            layoutParams = matchWrap().apply { topMargin = dp(10) }
        }

    private fun commandButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 11f
            setTextColor(white)
            backgroundTintList = ColorStateList.valueOf(surface2)
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(0, dp(66), 1f).apply {
                setMargins(dp(3), dp(4), dp(3), 0)
            }
        }

    private fun actionButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 11f
            backgroundTintList = ColorStateList.valueOf(surface2)
            setTextColor(white)
            setOnClickListener { action() }
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
                setMargins(dp(3), dp(5), dp(3), 0)
            }
        }

    private fun progress(value: Int, maximum: Int): ProgressBar {
        return ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = max(1, maximum)
            progress = value.coerceIn(0, max)
            progressTintList = ColorStateList.valueOf(green)
            progressBackgroundTintList = ColorStateList.valueOf(Color.parseColor("#28483B"))
            layoutParams = matchWrap().apply {
                height = dp(9)
                topMargin = dp(4)
            }
        }
    }

    private fun bigText(value: String, size: Float = 22f): TextView =
        TextView(this).apply {
            text = value
            setTextColor(white)
            textSize = size
            setTypeface(typeface, Typeface.BOLD)
        }

    private fun smallText(value: String): TextView =
        TextView(this).apply {
            text = value
            setTextColor(muted)
            textSize = 13f
            setPadding(0, dp(3), 0, dp(3))
        }

    private fun labelText(value: String, color: Int): TextView =
        TextView(this).apply {
            text = value
            setTextColor(color)
            textSize = 11f
            letterSpacing = 0.12f
            setTypeface(typeface, Typeface.BOLD)
        }

    private fun space(height: Int): Space =
        Space(this).apply { layoutParams = LinearLayout.LayoutParams(1, dp(height)) }

    private fun matchWrap(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

    private fun rounded(color: Int, radiusDp: Int): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dp(radiusDp).toFloat()
            setColor(color)
        }

    private fun cellDrawable(mine: Boolean): GradientDrawable =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dp(12).toFloat()
            setColor(Color.TRANSPARENT)
            setStroke(dp(if (mine) 4 else 1), if (mine) gold else Color.argb(90, 255, 255, 255))
        }

    private fun gradientDrawable(top: String, bottom: String): GradientDrawable =
        GradientDrawable(
            GradientDrawable.Orientation.TOP_BOTTOM,
            intArrayOf(Color.parseColor(top), Color.parseColor(bottom))
        )

    private fun withAlpha(color: Int, alpha: Int): Int =
        Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color))

    private fun t(source: String): String = language.t(source)

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun dayLabel(battle: Battle): String {
        val planted = battle.plantedAt ?: return statusHuman(battle.status)
        return runCatching {
            val from = OffsetDateTime.parse(planted)
            val days = ChronoUnit.DAYS.between(from, OffsetDateTime.now()).coerceAtLeast(0) + 1
            if (battle.growDays > 0) t("день ") + days + "/" + battle.growDays else t("день ") + days
        }.getOrDefault(statusHuman(battle.status))
    }

    @Suppress("DEPRECATION")
    private fun appVersionLabel(): String = runCatching {
        val info = packageManager.getPackageInfo(packageName, 0)
        t("Версия ") + (info.versionName ?: "?") + " (build " + info.versionCode + ")"
    }.getOrDefault(t("Версия ?"))

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }
}
