package farm.kisamore.battle

import android.app.Activity
import android.app.AlertDialog
import android.content.res.ColorStateList
import android.content.Intent
import android.provider.DocumentsContract
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Build
import android.view.WindowInsets
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
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
    private lateinit var contentHost: FrameLayout
    private lateinit var navBar: LinearLayout

    private var publicBattles: List<Battle> = emptyList()
    private var myBattles: List<Battle> = emptyList()
    private var currentScreen = "home"
    private val avatarRequestCode = 4201
    private var currentBattleId: String? = null

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
            setPadding(dp(8), 0, dp(8), 0)
            setBackgroundColor(Color.WHITE)
        }
        addNavigation()
        root.addView(navBar, LinearLayout.LayoutParams(-1, dp(48)))
        // Android 15+ draws app content behind system bars. Inset the entire
        // layout (including bottom tabs) explicitly to protect header and labels.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            window.statusBarColor = Color.TRANSPARENT
            window.navigationBarColor = Color.TRANSPARENT
            root.setOnApplyWindowInsetsListener { view, insets ->
                val bars = insets.getInsets(
                    WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars()
                )
                view.setPadding(0, bars.top, 0, bars.bottom)
                insets
            }
        } else {
            window.statusBarColor = Color.parseColor("#F8F9F6")
            window.navigationBarColor = Color.WHITE
        }
        window.decorView.systemUiVisibility =
            View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        setContentView(root)
    }

    private fun addNavigation() {
        navBar.removeAllViews()
        navBar.setBackgroundColor(Color.parseColor(if (
            getSharedPreferences("battle_settings", MODE_PRIVATE).getBoolean("dark_mode", false)
        ) "#1B2A22" else "#FFFFFF"))
        val english = getSharedPreferences("battle_settings", MODE_PRIVATE)
            .getString("language", "ru") == "en"
        val language = getSharedPreferences("battle_settings", MODE_PRIVATE)
            .getString("language", "ru") ?: "ru"
        val navLabels = mapOf(
            "ru" to listOf("Моё растение", "Битва", "История", "Профиль"),
            "en" to listOf("My plant", "Battle", "History", "Profile"),
            "zh" to listOf("我的植物", "对战", "历史", "个人"),
            "de" to listOf("Meine Pflanze", "Kampf", "Verlauf", "Profil"),
            "fr" to listOf("Ma plante", "Bataille", "Historique", "Profil"),
            "es" to listOf("Mi planta", "Batalla", "Historial", "Perfil"),
            "it" to listOf("La mia pianta", "Sfida", "Cronologia", "Profilo"),
            "pt" to listOf("Minha planta", "Batalha", "Histórico", "Perfil"),
            "pl" to listOf("Moja roślina", "Bitwa", "Historia", "Profil")
        )[language] ?: listOf("My plant", "Battle", "History", "Profile")
        val tabs = listOf(
            Triple(navLabels[0], "plant", "plant"),
            Triple(navLabels[1], "battle", "watch"),
            Triple(navLabels[2], "history", "history"),
            Triple(navLabels[3], "profile", "profile")
        )
        tabs.forEach { (label, icon, destination) ->
            val active = when (destination) {
                "plant" -> currentScreen in listOf("battle", "no_battle", "login")
                "watch" -> currentScreen in listOf("home", "watch")
                else -> currentScreen == destination
            }
            navBar.addView(BattleBottomTab(this, label, icon, active) {
                stopAutoRefresh()
                when (destination) {
                    "plant" -> {
                        val mine = activeMyBattle()
                        if (mine == null) {
                            if (api.hasSession()) showNoBattle() else showLogin()
                        } else openBattle(mine)
                    }
                    "watch" -> { currentScreen = "watch"; showWatch() }
                    "history" -> { currentScreen = "history"; showBattleHistory() }
                    "profile" -> { currentScreen = "profile"; showProfile() }
                }
                addNavigation()
            }, LinearLayout.LayoutParams(0, -1, 1f))
        }
    }

    private fun showBattleHistory() {
        currentScreen = "history"
        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader("История", "Ваши битвы"))
        val past = myBattles.filter { it.status == "finished" }
        if (past.isEmpty()) {
            val note = card()
            note.addView(bigText("История пока пуста", 18f))
            note.addView(smallText("Завершённые битвы появятся здесь."))
            body.addView(cardWithMargin(note))
        } else past.forEach { body.addView(battleListCard(it)) }
        showContent(scroll)
    }

    private fun pickProfilePhoto() {
        if (!api.hasSession()) { showLogin(); return }
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "image/*"
        }
        startActivityForResult(intent, avatarRequestCode)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == avatarRequestCode && resultCode == RESULT_OK) {
            val uri = data?.data ?: return
            try {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                val userId = api.currentUser?.id ?: return
                getSharedPreferences("battle_profile_photos", MODE_PRIVATE).edit()
                    .putString("avatar_" + userId, uri.toString()).apply()
                // Convert to a compact JPEG for the server's 2 MB upload limit.
                val bitmap = contentResolver.openInputStream(uri)?.use {
                    android.graphics.BitmapFactory.decodeStream(it)
                } ?: throw IllegalStateException("Не удалось прочитать фотографию")
                val compressed = java.io.ByteArrayOutputStream()
                var quality = 85
                val width = bitmap.width
                val height = bitmap.height
                val factor = minOf(1.0, 768.0 / maxOf(width, height))
                val sized = if (factor < 1.0)
                    android.graphics.Bitmap.createScaledBitmap(bitmap, (width * factor).toInt().coerceAtLeast(1),
                        (height * factor).toInt().coerceAtLeast(1), true) else bitmap
                do {
                    compressed.reset()
                    sized.compress(android.graphics.Bitmap.CompressFormat.JPEG, quality, compressed)
                    quality -= 10
                } while (compressed.size() > 2_097_152 && quality >= 30)
                val upload = compressed.toByteArray()
                async(work = { api.uploadAvatar(upload, "image/jpeg") }, success = {
                    accountPrefsLoadedFor = null
                    accountAvatarUrl = null
                    showProfile()
                }, failure = {
                    toast("Фото сохранено на телефоне, но не синхронизировано: " + it.message)
                    showProfile()
                })
            } catch (e: Exception) {
                toast("Не удалось сохранить фотографию: " + (e.message ?: "ошибка"))
            }
        }
    }

    private fun loadAll(target: String) {
        currentScreen = target
        showLoading("Подключаемся к теплице…")
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
        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader("KISAMORE BATTLE", "Настоящее растение. Ваши решения."))

        val profile = game.profile()
        body.addView(
            statStrip(
                "LEVEL " + profile.level,
                profile.xp.toString() + " XP",
                "🔥 " + profile.streak + " дн."
            )
        )

        val active = activeMyBattle()
        if (active != null) {
            body.addView(sectionTitle("ВАША БИТВА", "Продолжить игру"))
            body.addView(battleHeroCard(active, true))
        } else {
            body.addView(sectionTitle("СЕЙЧАС", if (api.hasSession()) "У вас нет активной битвы" else "Войдите, чтобы управлять растением"))
            val card = card()
            card.addView(bigText(if (api.hasSession()) "Выберите следующую битву 🌱" else "Станьте игроком 🌱"))
            card.addView(
                smallText(
                    if (api.hasSession())
                        "Пока можно наблюдать за другими участниками, смотреть таймлапсы и делать прогнозы."
                    else
                        "Участник получает настоящее растение и ограниченный запас воды, питания и времени без света."
                )
            )
            card.addView(primaryButton(if (api.hasSession()) "СМОТРЕТЬ БИТВЫ" else "ВОЙТИ В ИГРУ") {
                if (api.hasSession()) {
                    currentScreen = "watch"
                    showWatch()
                } else {
                    showLogin()
                }
            })
            body.addView(cardWithMargin(card))
        }

        body.addView(sectionTitle("ЗАДАНИЯ НА СЕГОДНЯ", "Короткие действия дают XP"))
        body.addView(missionsCard(profile))

        val live = publicBattles.firstOrNull { it.status in listOf("growing", "judging", "planting") }
        if (live != null && live.id != active?.id) {
            body.addView(sectionTitle("LIVE", "За этой битвой можно следить прямо сейчас"))
            body.addView(battleHeroCard(live, false))
        }

        body.addView(sectionTitle("ЗАЧЕМ ВОЗВРАЩАТЬСЯ", "Игра продолжается, пока растение растёт"))
        val info = card()
        info.addView(infoLine("📸", "Новое фото", "Смотрите изменения всей полки каждый день"))
        info.addView(infoLine("🎯", "Прогнозы", "Угадайте победителя раньше остальных"))
        info.addView(infoLine("🎬", "Таймлапсы", "Несколько дней роста за несколько секунд"))
        info.addView(infoLine("🏅", "XP и серии", "Возвращайтесь ежедневно и собирайте достижения"))
        body.addView(cardWithMargin(info))

        showContent(scroll)
    }

    private fun showWatch() {
        currentScreen = "watch"
        currentBattleId = null
        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader("LIVE АРЕНА", "Наблюдайте, болейте, делайте прогнозы"))

        if (publicBattles.isEmpty()) {
            val empty = card()
            empty.addView(bigText("Пока нет активных битв"))
            empty.addView(smallText("После создания следующей битвы она автоматически появится здесь."))
            empty.addView(primaryButton("ОБНОВИТЬ") { loadAll("watch") })
            body.addView(cardWithMargin(empty))
        } else {
            publicBattles.forEach { battle ->
                body.addView(battleListCard(battle))
            }
        }

        showContent(scroll)
    }

    private fun fallbackBattleProfile(battles: List<Battle>): PlayerBattleProfile {
        val finished = battles.filter { it.status == "finished" }
        val completedEntries = finished.flatMap { battle ->
            battle.entries.filter { it.isMine }.map { entry -> Pair(battle, entry) }
        }
        val wins = completedEntries.count { (_, entry) -> entry.isWinner }
        val rewards = completedEntries.flatMap { (battle, entry) ->
            val earned = battle.finishedAt ?: battle.createdAt ?: ""
            buildList {
                if (entry.isWinner) {
                    add(ServerReward("winner:" + entry.id, "Лучший садовод", "award", earned, null))
                    add(ServerReward("kisa:" + entry.id,
                        battle.winnerRewardKisa.toString() + " Kisa", "coins", earned, null))
                }
                if (entry.certificateUrl != null) {
                    add(ServerReward("diploma:" + entry.id,
                        "QR-диплом", "qr-code", earned, entry.certificateUrl))
                }
            }
        }.sortedByDescending { it.earnedAt }
        return PlayerBattleProfile(
            battleCount = battles.distinctBy { it.id }.size,
            winCount = wins,
            ratingPoints = completedEntries.size * 10 + wins * 100,
            rewards = rewards,
            finishedBattleIds = finished.map { it.id }
        )
    }

    private var cachedServerProfile: PlayerBattleProfile? = null

    private var accountAvatarUrl: String? = null
    private var accountPrefsLoadedFor: String? = null

    private fun syncPreference(language: String?, dark: Boolean?) {
        if (!api.hasSession()) return
        async(work = { api.savePreferences(language, dark) }, success = {
            applyRemotePreferences(it)
        }, failure = { toast("Не удалось сохранить настройки на сервере") })
    }

    private fun applyRemotePreferences(data: org.json.JSONObject) {
        getSharedPreferences("battle_settings", MODE_PRIVATE).edit()
            .putString("language", data.optString("language", "ru"))
            .putBoolean("dark_mode", data.optString("theme", "light") == "dark")
            .apply()
        accountAvatarUrl = api.absolute(data.optString("avatar_url").takeIf { it.isNotBlank() })
        accountPrefsLoadedFor = api.currentUser?.id
    }

    private fun showProfile() {
        currentScreen = "profile"
        currentBattleId = null
        val user = api.currentUser
        val localAvatar = user?.id?.let {
            getSharedPreferences("battle_profile_photos", MODE_PRIVATE).getString("avatar_" + it, null)
        }
        val avatar = if (user != null && accountPrefsLoadedFor == user.id)
            accountAvatarUrl ?: localAvatar else localAvatar
        fun render(server: PlayerBattleProfile?) {
            if (currentScreen != "profile") return
            showContent(BattleProfileScreen(
                this, user, game.profile(), myBattles, avatar, server,
                onChangePhoto = { pickProfilePhoto() },
                onLogin = { showLogin() },
                onPlant = {
                    val battle = activeMyBattle()
                    if (battle != null) openBattle(battle) else showNoBattle()
                    addNavigation()
                },
                onHistory = { showBattleHistory(); addNavigation() },
                onRegion = {
                    api.setRegion(!api.isRussianServer())
                    loadAll("profile")
                },
                onLogout = {
                    async(work = { api.logout(); true }, success = {
                        myBattles = emptyList()
                        cachedServerProfile = null
                        accountAvatarUrl = null
                        accountPrefsLoadedFor = null
                        showProfile()
                    })
                },
                onThemeChanged = { showProfile() },
                onLanguageChanged = { showProfile() },
                onPreferenceChanged = { language, dark -> syncPreference(language, dark) }
            ))
            addNavigation()
        }
        render(if (user == null) null else cachedServerProfile)
        if (user != null) {
            async(work = {
                // Refresh ownership, single-slot photos and completed battles together.
                val freshBattles = api.myBattles()
                val preferences = runCatching { api.fetchPreferences() }.getOrNull()
                val profileResponse = try { api.myBattleProfile() }
                catch (error: ApiException) {
                    if (error.statusCode != 404) throw error
                    // Older VPS supports /battles/me without a profile endpoint.
                    fallbackBattleProfile(freshBattles)
                }
                Triple(freshBattles, profileResponse, preferences)
            }, success = {
                myBattles = it.first
                cachedServerProfile = it.second
                if (it.third != null && accountPrefsLoadedFor != user.id) {
                    applyRemotePreferences(it.third!!)
                    showProfile()
                } else {
                    render(it.second)
                }
            }, failure = {
                cachedServerProfile = null
                render(null)
                toast("Не удалось загрузить статистику профиля")
            })
        }
    }

    private fun showLogin() {
        stopAutoRefresh()
        currentScreen = "login"
        currentBattleId = null

        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader("ВХОД В BATTLE", "Ваш аккаунт KisaMore"))

        val form = card()
        val email = EditText(this).apply {
            hint = "Email"
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            backgroundTintList = ColorStateList.valueOf(green)
        }
        val password = EditText(this).apply {
            hint = "Пароль"
            setHintTextColor(muted)
            setTextColor(white)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            backgroundTintList = ColorStateList.valueOf(green)
        }
        form.addView(email, matchWrap())
        form.addView(password, matchWrap())
        form.addView(space(10))
        form.addView(primaryButton("ВОЙТИ") {
            if (email.text.isBlank() || password.text.isBlank()) {
                toast("Введите email и пароль")
            } else {
                showLoading("Входим в игру…")
                async(
                    work = {
                        val loggedIn = api.login(email.text.toString(), password.text.toString())
                        val preferences = runCatching { api.fetchPreferences() }.getOrNull()
                        Pair(loggedIn, preferences)
                    },
                    success = {
                        game.openToday()
                        accountPrefsLoadedFor = null
                        if (it.second != null) applyRemotePreferences(it.second!!)
                        loadAll("home")
                    }
                )
            }
        })
        form.addView(smallText("Сервер: " + api.baseUrl))
        body.addView(cardWithMargin(form))
        showContent(scroll)
    }

    private fun showNoBattle() {
        currentScreen = "mine-empty"
        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(gameHeader("МОЯ БИТВА", "Активного растения пока нет"))
        val c = card()
        c.addView(bigText("Следующая битва ждёт 🌱"))
        c.addView(smallText("Выберите открытую битву. После покупки места здесь появятся фото растения, ресурсы и кнопки управления."))
        c.addView(primaryButton("ВЫБРАТЬ БИТВУ") {
            currentScreen = "watch"
            showWatch()
        })
        body.addView(cardWithMargin(c))
        showContent(scroll)
    }

    private fun openBattle(battle: Battle) {
        currentScreen = "battle"
        currentBattleId = battle.id
        showLoading("Открываем арену…")
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
        if (!silent) showLoading("Обновляем арену…")
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

        val scroll = screenScroll()
        val body = scroll.getChildAt(0) as LinearLayout
        body.addView(arenaHeader(battle))
        body.addView(shelfPhoto(battle))

        val mineEntries = battle.entries.filter { it.isMine }
        if (mineEntries.isNotEmpty()) {
            body.addView(sectionTitle("ВАШИ РАСТЕНИЯ", "Ресурсы скрыты от соперников до финала"))
            mineEntries.forEach { entry ->
                body.addView(resourceCard(battle, entry))
            }
        } else if (battle.status == "open") {
            body.addView(sectionTitle("СТАТЬ ИГРОКОМ", "В битве ещё есть места"))
            val join = card()
            join.addView(bigText("Свободно мест: " + battle.remainingEntries, 18f))
            join.addView(smallText("После участия вы получите собственный контейнер и сможете управлять его ресурсами."))
            join.addView(primaryButton(if (api.hasSession()) "ЗАНЯТЬ МЕСТО" else "ВОЙТИ И УЧАСТВОВАТЬ") {
                if (!api.hasSession()) {
                    showLogin()
                } else {
                    confirmJoin(battle)
                }
            })
            body.addView(cardWithMargin(join))
        }

        body.addView(sectionTitle("ПРОГНОЗ ЗРИТЕЛЕЙ", "Кто победит в этой битве?"))
        body.addView(predictionCard(battle))

        body.addView(sectionTitle("ТАЙМЛАПС", "Рост, который не нужно ждать часами"))
        body.addView(timelapseCard(battle))

        body.addView(sectionTitle("СОБЫТИЯ", "Что происходит прямо сейчас"))
        body.addView(eventFeed(battle))

        showContent(scroll)
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
        textBlock.addView(labelText("● LIVE BATTLE", green))
        textBlock.addView(bigText(battle.title, 27f))
        textBlock.addView(smallText(battle.plantName + " · полка " + battle.rackId + " · " + dayLabel(battle)))
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

    private fun shelfPhoto(battle: Battle): View {
        val frame = FrameLayout(this).apply {
            background = rounded(surface2, 22)
            clipToOutline = true
        }
        val image = ImageView(this).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            setBackgroundColor(surface2)
            contentDescription = "Фото полки"
        }
        frame.addView(
            image,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(260)
            )
        )

        val grid = GridLayout(this).apply {
            rowCount = 3
            columnCount = 2
            setPadding(dp(5), dp(5), dp(5), dp(5))
        }
        repeat(6) { index ->
            val slot = index + 1
            val entry = battle.entries.firstOrNull { it.slotNumber == slot }
            val mine = entry?.isMine == true
            val cell = TextView(this).apply {
                text = if (mine) "#" + slot + "  ★ ВЫ" else "#" + slot
                gravity = Gravity.TOP or Gravity.START
                setPadding(dp(8), dp(7), dp(4), dp(4))
                setTextColor(if (mine) gold else white)
                textSize = 11f
                setTypeface(typeface, Typeface.BOLD)
                background = cellDrawable(mine)
            }
            val params = GridLayout.LayoutParams(
                GridLayout.spec(index / 2, 1f),
                GridLayout.spec(index % 2, 1f)
            ).apply {
                width = 0
                height = 0
                setMargins(dp(3), dp(3), dp(3), dp(3))
            }
            grid.addView(cell, params)
        }
        frame.addView(
            grid,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(260)
            )
        )

        async(
            work = { api.loadBitmap(api.absolute(battle.rackPhotoUrl)) },
            success = { bitmap -> if (bitmap != null) image.setImageBitmap(bitmap) },
            failure = { }
        )

        return FrameLayout(this).apply {
            setPadding(dp(16), dp(8), dp(16), dp(4))
            addView(
                frame,
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    dp(260)
                )
            )
        }
    }

    private fun resourceCard(battle: Battle, entry: BattleEntry): View {
        val c = card()
        c.addView(bigText("🌱 Контейнер #" + entry.slotNumber, 19f))
        c.addView(smallText(if (battle.status == "growing") "Вы принимаете решения" else statusHuman(battle.status)))
        c.addView(space(8))
        c.addView(resourceRow("💧 Вода", battle.waterBudgetMl, entry.waterUsedMl, "мл"))
        c.addView(resourceRow("🧪 Питание", battle.nutrientBudgetMl, entry.nutrientUsedMl, "мл"))
        c.addView(resourceRow("🌙 Без света", battle.shadeBudgetMinutes, entry.shadeUsedMinutes, "мин"))

        if (battle.status == "growing") {
            c.addView(space(8))
            c.addView(labelText("ВАШ ХОД", gold))
            val actions = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
            }
            actions.addView(commandButton("💧\nПолить") { amountDialog(battle, entry, "water") })
            actions.addView(commandButton("🧪\nПитание") { amountDialog(battle, entry, "nutrient") })
            actions.addView(commandButton("🌙\nЗакрыть") { amountDialog(battle, entry, "shade") })
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
                text = (if (selected) "🌟 " else "🌱 ") + "Контейнер #" + entry.slotNumber
                setTextColor(if (selected) gold else white)
                textSize = 15f
                setTypeface(typeface, Typeface.BOLD)
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            row.addView(TextView(this).apply {
                text = votes.toString() + " голосов"
                setTextColor(muted)
                textSize = 12f
            })
            row.setOnClickListener {
                if (!api.hasSession()) {
                    showLogin()
                } else if (battle.status == "finished") {
                    toast("Прогнозы уже закрыты")
                } else {
                    sendPrediction(battle, entry)
                }
            }
            c.addView(row)
        }
        c.addView(space(7))
        c.addView(smallText("Можно менять выбор до окончания битвы. Прогноз не влияет на растение."))
        return cardWithMargin(c)
    }

    private fun timelapseCard(battle: Battle): View {
        val c = card()
        val preferred = battle.mine ?: battle.entries.firstOrNull()
        if (preferred == null) {
            c.addView(smallText("Таймлапс появится после посадки."))
            return cardWithMargin(c)
        }
        c.addView(bigText("Контейнер #" + preferred.slotNumber, 18f))
        val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        buttons.addView(actionButton("🎬 24 ЧАСА") {
            openVideo(preferred.timelapse24hUrl)
        })
        buttons.addView(actionButton("🎞 3 ДНЯ") {
            openVideo(preferred.timelapse3dUrl)
        })
        c.addView(buttons)
        return cardWithMargin(c)
    }

    private fun eventFeed(battle: Battle): View {
        val c = card()
        c.addView(eventLine("🌿", "Битва идёт", battle.plantName + " · " + dayLabel(battle)))
        if (battle.predictionTotal > 0) {
            c.addView(eventLine("🎯", "Зрители спорят о победителе", battle.predictionTotal.toString() + " прогнозов"))
        }
        if (battle.status == "open") {
            c.addView(eventLine("🎟", "Набор участников", "Свободно мест: " + battle.remainingEntries))
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
                    "Ваш ход · контейнер #" + entry.slotNumber,
                    actionHuman(action) + " · " + actionStatus(action.status)
                )
            )
        }
        if (ownActions.isEmpty() && battle.status == "growing") {
            c.addView(eventLine("⏳", "Следующий ход за вами", "Решите, стоит ли сейчас тратить ресурсы"))
        }
        return cardWithMargin(c)
    }

    private fun sendPrediction(battle: Battle, entry: BattleEntry) {
        toast("Сохраняем прогноз…")
        async(
            work = { api.predict(battle.id, entry.id) },
            success = { updated ->
                game.completeMission("predict")
                replaceBattleInCaches(updated)
                renderBattle(updated)
                toast("+10 XP · прогноз сохранён")
            },
            failure = { error ->
                if (error is ApiException && error.statusCode == 404) {
                    toast("Для прогнозов нужно обновить Battle API на сервере")
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
            hint = if (kind == "shade") "минуты" else "мл"
        }
        val presets = when (kind) {
            "water" -> intArrayOf(30, 60, 100)
            "nutrient" -> intArrayOf(5, 10, 20)
            else -> intArrayOf(30, 60, 120)
        }
        val title = when (kind) {
            "water" -> "💧 Полить растение"
            "nutrient" -> "🧪 Добавить питание"
            else -> "🌙 Закрыть от света"
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
            .setMessage("Это реальная команда. Ресурс будет списан из лимита растения.")
            .setView(wrap)
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Отправить") { _, _ ->
                val amount = input.text.toString().toIntOrNull() ?: 0
                if (amount <= 0) {
                    toast("Укажите количество")
                } else {
                    executeCommand(battle, entry, kind, amount)
                }
            }
            .show()
    }

    private fun executeCommand(battle: Battle, entry: BattleEntry, kind: String, amount: Int) {
        showLoading("Передаём команду в теплицу…")
        async(
            work = {
                api.sendAction(battle.id, entry.id, kind, amount)
                api.authenticatedBattle(battle.id)
            },
            success = { updated ->
                game.completeMission("command")
                replaceBattleInCaches(updated)
                renderBattle(updated)
                toast("+15 XP · команда принята")
            }
        )
    }

    private fun confirmJoin(battle: Battle) {
        AlertDialog.Builder(this)
            .setTitle("Занять место в битве?")
            .setMessage("Будет использована стоимость участия в Kisa. После покупки место закрепится за вашим аккаунтом.")
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Участвовать") { _, _ ->
                showLoading("Бронируем растение…")
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

    private fun openVideo(path: String?) {
        val url = api.absolute(path)
        if (url.isNullOrBlank()) {
            toast("Таймлапс пока не готов")
            return
        }
        game.completeMission("video")
        runCatching {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            toast("+5 XP · наблюдение засчитано")
        }.onFailure {
            toast("Не удалось открыть видео")
        }
    }

    private fun battleHeroCard(battle: Battle, mine: Boolean): View {
        val c = card()
        c.addView(labelText(if (mine) "🎮 ВЫ В ИГРЕ" else "● LIVE", if (mine) gold else green))
        c.addView(bigText(battle.title, 21f))
        c.addView(smallText(battle.plantName + " · " + dayLabel(battle)))
        c.addView(space(8))
        c.addView(statStrip(
            battle.entriesCount.toString() + "/" + battle.maxEntries,
            "🎯 " + battle.predictionTotal,
            "🏆 " + battle.winnerRewardKisa + " K"
        ))
        c.addView(primaryButton(if (mine) "ОТКРЫТЬ АРЕНУ" else "СМОТРЕТЬ LIVE") {
            openBattle(battle)
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
        names.addView(smallText(battle.plantName + " · полка " + battle.rackId))
        top.addView(names, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        top.addView(statusPill(battle.status))
        c.addView(top)
        c.addView(space(8))
        c.addView(statStrip(
            battle.entriesCount.toString() + "/" + battle.maxEntries + " 🌱",
            "🎯 " + battle.predictionTotal,
            if (battle.status == "open") battle.remainingEntries.toString() + " мест" else dayLabel(battle)
        ))
        c.setOnClickListener { openBattle(battle) }
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
                text = if (mission.completed) "Выполнено" else "+" + mission.reward + " XP"
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
        c.addView(smallText("Сегодня: " + done + "/" + profile.missions.size + " заданий"))
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
        val unit = if (action.kind == "shade") " мин" else " мл"
        return when (action.kind) {
            "water" -> "Полив " + action.amount + unit
            "nutrient" -> "Питание " + action.amount + unit
            "shade" -> "Без света " + action.amount + unit
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
        "pending" -> "ожидает выполнения"
        "completed" -> "выполнено"
        "cancelled" -> "отменено"
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
        val message = error.message ?: "Не удалось связаться с сервером"
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
            addView(labelText("KISAMORE", green))
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
        "open" -> "Набор"
        "ready_to_plant" -> "Готово к посадке"
        "planting" -> "Посадка"
        "growing" -> "Live"
        "judging" -> "Финал"
        "finished" -> "Завершено"
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

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun dayLabel(battle: Battle): String {
        val planted = battle.plantedAt ?: return statusHuman(battle.status)
        return runCatching {
            val from = OffsetDateTime.parse(planted)
            val days = ChronoUnit.DAYS.between(from, OffsetDateTime.now()).coerceAtLeast(0) + 1
            if (battle.growDays > 0) "день " + days + "/" + battle.growDays else "день " + days
        }.getOrDefault(statusHuman(battle.status))
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }
}
