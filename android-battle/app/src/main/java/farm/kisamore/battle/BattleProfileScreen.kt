package farm.kisamore.battle

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/**
 * The profile is intentionally one screen without scrolling. Cards SHARE the
 * available height using layout weights; only small fixed gaps separate them.
 * No view rebuilding during layout, and no weighted spacers between cards.
 */
class BattleProfileScreen(
    private val host: Activity,
    private val user: UserInfo?,
    private val profile: GameProfile,
    private val battles: List<Battle>,
    private val avatarUri: String?,
    private val serverProfile: PlayerBattleProfile? = null,
    private val onChangePhoto: () -> Unit,
    private val onLogin: () -> Unit,
    private val onPlant: () -> Unit,
    private val onPlantPhoto: (Battle) -> Unit = {},
    private val onHistory: () -> Unit,
    private val onRegion: () -> Unit,
    private val onLogout: () -> Unit,
    private val onThemeChanged: () -> Unit = {},
    private val onLanguageChanged: () -> Unit = {},
    private val onPreferenceChanged: (String?, Boolean?) -> Unit = { _, _ -> }
) : LinearLayout(host) {
    private val languageCodes = arrayOf("en", "ru", "zh", "de", "fr", "es", "it", "pt", "pl")
    private val languageNames = arrayOf("English", "Русский", "中文", "Deutsch", "Français", "Español", "Italiano", "Português", "Polski")
    private val night = host.getSharedPreferences("battle_settings", 0).getBoolean("dark_mode", false)
    private val languageCode = host.getSharedPreferences("battle_settings", 0).getString("language", "ru") ?: "ru"
    private val english = host.getSharedPreferences("battle_settings", 0).getString("language", "ru") == "en"
    private val translations: Map<String, Map<String, String>> = mapOf(
            "Гость" to mapOf("en" to "Guest", "zh" to "访客", "de" to "Gast", "fr" to "Invité", "es" to "Invitado", "it" to "Ospite", "pt" to "Visitante", "pl" to "Gość"),
            "Войдите в аккаунт" to mapOf("en" to "Sign in to your account", "zh" to "登录账号", "de" to "Bitte anmelden", "fr" to "Connectez-vous", "es" to "Inicia sesión", "it" to "Accedi al tuo account", "pt" to "Entre na sua conta", "pl" to "Zaloguj się"),
            "Войти" to mapOf("en" to "Sign in", "zh" to "登录", "de" to "Anmelden", "fr" to "Connexion", "es" to "Entrar", "it" to "Accedi", "pt" to "Entrar", "pl" to "Zaloguj się"),
            "Изменить фото" to mapOf("en" to "Change photo", "zh" to "更换照片", "de" to "Foto ändern", "fr" to "Changer la photo", "es" to "Cambiar foto", "it" to "Cambia foto", "pt" to "Alterar foto", "pl" to "Zmień zdjęcie"),
            "Битв" to mapOf("en" to "Battles", "zh" to "对战", "de" to "Kämpfe", "fr" to "Batailles", "es" to "Batallas", "it" to "Sfide", "pt" to "Batalhas", "pl" to "Bitwy"),
            "Побед" to mapOf("en" to "Wins", "zh" to "胜利", "de" to "Siege", "fr" to "Victoires", "es" to "Victorias", "it" to "Vittorie", "pt" to "Vitórias", "pl" to "Zwycięstwa"),
            "Рейтинг" to mapOf("en" to "Rating", "zh" to "积分", "de" to "Punkte", "fr" to "Classement", "es" to "Puntos", "it" to "Punteggio", "pt" to "Pontos", "pl" to "Ranking"),
            "Мои растения" to mapOf("en" to "My plants", "zh" to "我的植物", "de" to "Meine Pflanzen", "fr" to "Mes plantes", "es" to "Mis plantas", "it" to "Le mie piante", "pt" to "Minhas plantas", "pl" to "Moje rośliny"),
            "Пока нет растения" to mapOf("en" to "No plant yet", "zh" to "暂无植物", "de" to "Noch keine Pflanze", "fr" to "Aucune plante", "es" to "Sin plantas", "it" to "Nessuna pianta", "pt" to "Sem plantas", "pl" to "Brak roślin"),
            "Выбрать битву" to mapOf("en" to "Choose a battle", "zh" to "选择对战", "de" to "Kampf auswählen", "fr" to "Choisir une bataille", "es" to "Elegir batalla", "it" to "Scegli una sfida", "pt" to "Escolher batalha", "pl" to "Wybierz bitwę"),
            "Растёт" to mapOf("en" to "Growing", "zh" to "生长中", "de" to "Wächst", "fr" to "En croissance", "es" to "Creciendo", "it" to "In crescita", "pt" to "Crescendo", "pl" to "Rośnie"),
            "Участие в битве" to mapOf("en" to "Participating", "zh" to "参与中", "de" to "Teilnahme", "fr" to "Participation", "es" to "Participando", "it" to "In gara", "pt" to "Participando", "pl" to "Uczestniczy"),
            "Награды" to mapOf("en" to "Rewards", "zh" to "奖励", "de" to "Auszeichnungen", "fr" to "Récompenses", "es" to "Recompensas", "it" to "Premi", "pt" to "Recompensas", "pl" to "Nagrody"),
            "Все награды  ›" to mapOf("en" to "All rewards  ›", "zh" to "全部奖励  ›", "de" to "Alle Auszeichnungen  ›", "fr" to "Récompenses  ›", "es" to "Ver todas  ›", "it" to "Tutti i premi  ›", "pt" to "Todas  ›", "pl" to "Wszystkie  ›"),
            "История битв" to mapOf("en" to "Battle history", "zh" to "对战历史", "de" to "Kampfverlauf", "fr" to "Historique", "es" to "Historial", "it" to "Cronologia", "pt" to "Histórico", "pl" to "Historia bitew"),
            "Все битвы  ›" to mapOf("en" to "All battles  ›", "zh" to "全部对战  ›", "de" to "Alle Kämpfe  ›", "fr" to "Toutes  ›", "es" to "Todas  ›", "it" to "Tutte  ›", "pt" to "Todas  ›", "pl" to "Wszystkie  ›"),
            "Пока нет завершённых битв" to mapOf("en" to "No finished battles yet", "zh" to "暂无已完成对战", "de" to "Noch keine beendeten Kämpfe", "fr" to "Aucune bataille terminée", "es" to "No hay batallas finalizadas", "it" to "Nessuna sfida conclusa", "pt" to "Nenhuma batalha concluída", "pl" to "Brak zakończonych bitew"),
            "Наград пока нет" to mapOf("en" to "No rewards yet", "zh" to "暂无奖励", "de" to "Noch keine Auszeichnungen", "fr" to "Aucune récompense", "es" to "Sin recompensas", "it" to "Nessun premio", "pt" to "Sem recompensas", "pl" to "Brak nagród"),
            "Нет данных о наградах" to mapOf("en" to "Rewards unavailable", "zh" to "无法加载奖励", "de" to "Auszeichnungen nicht verfügbar", "fr" to "Récompenses indisponibles", "es" to "Premios no disponibles", "it" to "Premi non disponibili", "pt" to "Recompensas indisponíveis", "pl" to "Nagrody niedostępne"),
            "Настройки" to mapOf("en" to "Settings", "zh" to "设置", "de" to "Einstellungen", "fr" to "Paramètres", "es" to "Ajustes", "it" to "Impostazioni", "pt" to "Configurações", "pl" to "Ustawienia"),
            "Уведомления" to mapOf("en" to "Notifications", "zh" to "通知", "de" to "Benachrichtigungen", "fr" to "Notifications", "es" to "Notificaciones", "it" to "Notifiche", "pt" to "Notificações", "pl" to "Powiadomienia"),
            "Тёмная тема" to mapOf("en" to "Dark theme", "zh" to "深色模式", "de" to "Dunkles Design", "fr" to "Thème sombre", "es" to "Tema oscuro", "it" to "Tema scuro", "pt" to "Tema escuro", "pl" to "Ciemny motyw"),
            "Язык" to mapOf("en" to "Language", "zh" to "语言", "de" to "Sprache", "fr" to "Langue", "es" to "Idioma", "it" to "Lingua", "pt" to "Idioma", "pl" to "Język"),
            "Помощь" to mapOf("en" to "Help", "zh" to "帮助", "de" to "Hilfe", "fr" to "Aide", "es" to "Ayuda", "it" to "Aiuto", "pt" to "Ajuda", "pl" to "Pomoc"),
    )
    private fun tr(ru: String, en: String): String = when (languageCode) {
        "ru" -> ru
        "en" -> en
        else -> translations[ru]?.get(languageCode) ?: en
    }
    private val ink = Color.parseColor(if (night) "#F2F6F2" else "#1A1C1A")
    private val secondary = Color.parseColor(if (night) "#ACB8AD" else "#6B7268")
    private val accent = Color.parseColor(if (night) "#8CC89E" else "#4A7C59")
    private val olive = Color.parseColor(if (night) "#9AB99B" else "#8B9A7D")
    private val pale = Color.parseColor(if (night) "#273E2F" else "#E8F0E8")
    private val bg = Color.parseColor(if (night) "#101A14" else "#F8F9F6")
    private val shortScreen = resources.configuration.screenHeightDp < 715
    private val padding = if (shortScreen) 9 else 12
    private val gapSize = if (shortScreen) 3 else 5

    init {
        orientation = VERTICAL
        setBackgroundColor(bg)
        setPadding(dp(16), dp(6), dp(16), dp(6))
        populate()
    }

    private fun populate() {
        // Natural content heights instead of weights filling the screen.
        addView(profileCard(), LayoutParams(-1, dp(if (shortScreen) 82 else 99)))
        gap()
        addView(statsRow(), LayoutParams(-1, dp(if (shortScreen) 52 else 58)))
        gap()
        addView(plantCard(), LayoutParams(-1, dp(if (shortScreen) 83 else 99)))
        gap()
        addView(rewardsCard(), LayoutParams(-1, dp(if (shortScreen) 77 else 99)))
        gap()
        addView(historyCard(), LayoutParams(-1, dp(if (shortScreen) 77 else 99)))
        gap()
        addView(settingsCard(), LayoutParams(-1, dp(if (shortScreen) 149 else 209)))
    }

    private fun profileCard(): View {
        val card = card(padding).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val avatarSize = if (shortScreen) 56 else 68
        val avatarHolder = FrameLayout(host)
        avatarHolder.addView(text(
            user?.displayName?.firstOrNull()?.uppercaseChar()?.toString() ?: "K",
            if (shortScreen) 27f else 32f, accent, true
        ).apply {
            gravity = Gravity.CENTER
            background = rounded(pale, avatarSize / 2)
            setOnClickListener { changePhoto() }
        }, FrameLayout.LayoutParams(dp(avatarSize), dp(avatarSize)))

        if (!avatarUri.isNullOrBlank()) {
            val portrait = ImageView(host).apply {
                scaleType = ImageView.ScaleType.CENTER_CROP
                background = rounded(pale, avatarSize / 2)
                clipToOutline = true
                contentDescription = "Изменить фотографию"
                setOnClickListener { changePhoto() }
            }
            if (avatarUri.startsWith("http")) {
                PhotoFrameCache.showPrevious(portrait, avatarUri)
                loadRemoteAvatar(portrait, avatarUri)
                avatarHolder.addView(portrait, FrameLayout.LayoutParams(dp(avatarSize), dp(avatarSize)))
            } else if (loadAvatar(portrait, avatarUri)) {
                avatarHolder.addView(portrait, FrameLayout.LayoutParams(dp(avatarSize), dp(avatarSize)))
            }
        }

        if (user != null) avatarHolder.addView(FrameLayout(host).apply {
            background = rounded(accent, 20)
            addView(icon("camera", 18, Color.WHITE),
                FrameLayout.LayoutParams(dp(18), dp(18), Gravity.CENTER))
            setOnClickListener { changePhoto() }
            contentDescription = "Загрузить фотографию"
        }, FrameLayout.LayoutParams(dp(25), dp(25), Gravity.END or Gravity.BOTTOM))
        card.addView(avatarHolder, LayoutParams(dp(avatarSize), dp(avatarSize)))

        val details = column().apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), 0, 0, 0)
        }
        details.addView(text(user?.displayName ?: tr("Гость", "Guest"), if (shortScreen) 20f else 23f, ink, true, true))
        details.addView(text(user?.email ?: tr("Войдите в аккаунт", "Sign in to your account"), 12f, secondary, single = true))
        details.addView(text(if (user == null) tr("Войти", "Sign in") else tr("Изменить фото", "Change photo"), 13f, accent).apply {
            setPadding(0, dp(4), 0, 0)
            setOnClickListener { changePhoto() }
        })
        profile.badges.firstOrNull()?.let { badge ->
            details.addView(text("♛  " + badge, 11f, accent, single = true).apply {
                background = rounded(pale, 15)
                setPadding(dp(7), dp(3), dp(7), dp(3))
            }, LayoutParams(-2, -2).apply { topMargin = dp(4) })
        }
        card.addView(details, LayoutParams(0, -2, 1f))
        if (user != null) {
            card.addView(icon("logout", 22, secondary).apply {
                contentDescription = "Выйти из профиля"
                setOnClickListener { confirmLogout() }
            }, LayoutParams(dp(26), dp(28)))
        }
        return card
    }

    private fun statsRow(): View {
        val row = row()
        val values = listOf(
            Triple("battle", tr("Битв", "Battles"), if (user == null) "0" else serverProfile?.battleCount?.toString() ?: "—"),
            Triple("trophy", tr("Побед", "Wins"), if (user == null) "0" else serverProfile?.winCount?.toString() ?: "—"),
            Triple("chart", tr("Рейтинг", "Rating"), if (user == null) "0" else serverProfile?.ratingPoints?.toString() ?: "—")
        )
        values.forEachIndexed { i, item ->
            val box = card(if (shortScreen) 7 else 10).apply {
                orientation = HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            box.addView(icon(item.first, if (shortScreen) 19 else 23, olive),
                LayoutParams(dp(if (shortScreen) 25 else 30), dp(if (shortScreen) 30 else 36)))
            val valuesColumn = column().apply {
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(6), 0, 0, 0)
            }
            valuesColumn.addView(text(item.second, if (shortScreen) 10f else 11f, secondary, single = true))
            valuesColumn.addView(text(item.third, if (shortScreen) 20f else 24f, ink, true))
            box.addView(valuesColumn, LayoutParams(0, -2, 1f))
            row.addView(box, LayoutParams(0, -1, 1f).apply {
                if (i < values.lastIndex) rightMargin = dp(6)
            })
        }
        return row
    }

    private fun plantCard(): View {
        val card = card(padding).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setOnClickListener { onPlant() }
        }
        val battle = battles.firstOrNull { it.mine != null && it.status != "finished" }
        val dimension = if (shortScreen) 48 else 60
        val thumb = ImageView(host).apply {
            background = rounded(pale, 12)
            scaleType = ImageView.ScaleType.CENTER_CROP
            clipToOutline = true
            // No placeholder icon: keep this empty until a real photo arrives.
        }
        thumb.visibility = View.GONE
        card.addView(thumb, LayoutParams(dp(dimension * 2), dp(dimension)))
        if (battle != null) {
            thumb.isClickable = true
            thumb.contentDescription = "Открыть фотографию растения"
            thumb.setOnClickListener { onPlantPhoto(battle) }
        }
        // Slot-specific cropped image; never show the whole rack in the plant card.
        battle?.mine?.photoUrl?.let { url ->
            ApiClient(host.applicationContext).absolute(url)?.let { resolved ->
                if (PhotoFrameCache.current(resolved) != null) {
                    PhotoFrameCache.showPrevious(thumb, resolved)
                    thumb.visibility = View.VISIBLE
                }
            }
            loadPlantPhoto(thumb, url)
        }

        val info = column().apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(11), 0, dp(5), 0)
        }
        info.addView(text(tr("Мои растения", "My plants"), if (shortScreen) 16f else 18f, ink, true, true))
        info.addView(text(battle?.plantName ?: tr("Пока нет растения", "No plant yet"), 13f, secondary, single = true))
        info.addView(text(
            if (battle == null) tr("Выбрать битву", "Choose a battle") else
                if (battle.status == "growing") tr("Растёт", "Growing") else tr("Участие в битве", "Participating"),
            11f, accent, single = true
        ))
        card.addView(info, LayoutParams(0, -2, 1f))
        card.addView(icon("chevron", 18, secondary), LayoutParams(dp(18), dp(18)))
        return card
    }

    private fun rewardsCard(): View {
        val card = card(if (shortScreen) 9 else 12)
        card.addView(heading(tr("Награды", "Rewards"), tr("Все награды  ›", "All rewards  ›")) { showRewards() },
            LayoutParams(-1, dp(26)))
        val recent = serverProfile?.rewards?.take(3).orEmpty()
        if (recent.isEmpty()) {
            card.addView(text(if (user == null) tr("Наград пока нет", "No rewards yet") else
                if (serverProfile == null) tr("Нет данных о наградах", "Rewards unavailable") else tr("Наград пока нет", "No rewards yet"),
                13f, secondary), LayoutParams(-1, dp(23)))
        } else {
            val cells = row().apply { gravity = Gravity.CENTER_VERTICAL }
            recent.forEach { reward ->
                val cell = column().apply { gravity = Gravity.CENTER_HORIZONTAL }
                cell.addView(icon(when (reward.icon) {
                    "coins" -> "coins"
                    "qr-code" -> "qr-code"
                    "sprout" -> "plant"
                    else -> "award"
                }, 25, accent), LayoutParams(dp(28), dp(28)))
                cell.addView(text(reward.title, 10f, ink, single = true).apply {
                    gravity = Gravity.CENTER
                }, LayoutParams(-1, dp(18)))
                cell.setOnClickListener { showRewards() }
                cells.addView(cell, LayoutParams(0, -2, 1f))
            }
            card.addView(cells, LayoutParams(-1, -2))
        }
        return card
    }

    private fun historyCard(): View {
        val card = card(if (shortScreen) 7 else 10)
        card.addView(heading(tr("История битв", "Battle history"), tr("Все битвы  ›", "All battles  ›")) { onHistory() },
            LayoutParams(-1, dp(26)))
        val finished = battles.filter { it.status == "finished" &&
            (serverProfile?.finishedBattleIds?.contains(it.id) == true) }
        if (finished.isEmpty()) {
            card.addView(text(tr("Пока нет завершённых битв", "No finished battles yet"), 13f, secondary).apply {
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(6), 0, 0, 0)
            }, LayoutParams(-1, dp(30)))
        } else {
            finished.take(2).forEach { battle ->
                val row = row().apply {
                    gravity = Gravity.CENTER_VERTICAL
                    setPadding(dp(7), dp(1), dp(7), dp(1))
                    background = rounded(bg, 11)
                    setOnClickListener { onHistory() }
                }
                row.addView(text("✿", 16f, olive), LayoutParams(dp(24), -2))
                val copy = column()
                copy.addView(text(battle.plantName, 13f, ink, true, true))
                copy.addView(text("Завершена", 10f, secondary))
                row.addView(copy, LayoutParams(0, -2, 1f))
                row.addView(text("›", 17f, secondary))
                card.addView(row, LayoutParams(-1, dp(36)).apply { bottomMargin = dp(2) })
            }
        }
        return card
    }

    private fun settingsCard(): View {
        val card = card(if (shortScreen) 6 else 9)
        card.addView(heading(tr("Настройки", "Settings"), "") { settingsDialog() },
            LayoutParams(-1, dp(22)))
        val options = listOf(
            Triple("bell", tr("Уведомления", "Notifications"), "›"),
            Triple("moon", tr("Тёмная тема", "Dark theme"), ""),
            Triple("globe", tr("Язык", "Language"), languageNames[languageCodes.indexOf(languageCode).coerceAtLeast(0)] + " ›"),
            Triple("help", tr("Помощь", "Help"), "›")
        )
        options.forEachIndexed { i, item ->
            val line = row().apply {
                gravity = Gravity.CENTER_VERTICAL
                minimumHeight = dp(if (shortScreen) 26 else 37)
                // All settings rows share the same background.
                setOnClickListener { settingAction(i) }
            }
            line.addView(icon(item.first, 22, secondary), LayoutParams(dp(31), dp(23)))
            line.addView(text(item.second, if (shortScreen) 14f else 15f, ink), LayoutParams(0, -2, 1f))
            if (i == 1) {
                line.addView(android.widget.Switch(host).apply {
                    isChecked = host.getSharedPreferences("battle_settings", 0)
                        .getBoolean("dark_mode", false)
                    setOnCheckedChangeListener { _, enabled ->
                        host.getSharedPreferences("battle_settings", 0).edit()
                            .putBoolean("dark_mode", enabled).apply()
                        onPreferenceChanged(null, enabled)
                        onThemeChanged()
                    }
                })
            } else line.addView(text(item.third, if (shortScreen) 13f else 14f, secondary))
            card.addView(line, LayoutParams(-1, dp(if (shortScreen) 27 else 39)))
        }
        return card
    }

    private fun icon(glyph: String, size: Int, color: Int): View = BattleTabGlyph(host, glyph, color).apply {
        contentDescription = glyph
    }

    private fun heading(left: String, right: String, onClick: () -> Unit): View = row().apply {
        gravity = Gravity.CENTER_VERTICAL
        addView(text(left, if (shortScreen) 15f else 17f, ink, true),
            LayoutParams(0, -2, 1f))
        addView(text(right, 11f, secondary).apply { setOnClickListener { onClick() } })
    }

    private fun showRewards() {
        val trophies = serverProfile?.rewards.orEmpty()
        val actual = if (trophies.isEmpty()) "Наград пока нет." else
            trophies.joinToString("\n• ", "• ") { it.title }
        AlertDialog.Builder(host).setTitle("Мои награды")
            .setMessage(actual + "\n\nПосле участия доступен QR-диплом, за победу — 20 Kisa.")
            .setPositiveButton("Закрыть", null).show()
    }

    private fun settingAction(index: Int) {
        when (index) {
            0 -> try {
                host.startActivity(Intent("android.settings.APP_NOTIFICATION_SETTINGS").apply {
                    putExtra("android.provider.extra.APP_PACKAGE", host.packageName)
                })
            } catch (_: Exception) { }
            1 -> {
                val prefs = host.getSharedPreferences("battle_settings", 0)
                prefs.edit().putBoolean("dark_mode", !prefs.getBoolean("dark_mode", false)).apply()
                onPreferenceChanged(null, prefs.getBoolean("dark_mode", false))
                onThemeChanged()
            }
            2 -> AlertDialog.Builder(host).setTitle("Язык приложения")
                .setSingleChoiceItems(languageNames,
                    languageCodes.indexOf(languageCode).coerceAtLeast(0)) { dialog, which ->
                    val code = languageCodes[which]
                    host.getSharedPreferences("battle_settings", 0).edit()
                        .putString("language", code).apply()
                    dialog.dismiss()
                    onPreferenceChanged(code, null)
                    onLanguageChanged()
                }.setNegativeButton("Отмена", null).show()
            3 -> showHelp()
        }
    }

    private fun showHelp() {
        AlertDialog.Builder(host)
            .setTitle("О проекте KisaMore Battle")
            .setMessage("KisaMore Battle — соревнование по выращиванию настоящих растений. " +
                "У каждого участника свой контейнер, ограниченные ресурсы воды, питания " +
                "и управления освещением. Следите за ростом по фотографиям и таймлапсам, " +
                "принимайте решения и соревнуйтесь за награды.\\n\\n" +
                "У вас есть вопрос или предложение? Свяжитесь с командой проекта.")
            .setNegativeButton("Закрыть", null)
            .setPositiveButton("Задать вопрос") { _, _ ->
                val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:support@kisamore.farm"))
                try {
                    host.startActivity(intent)
                } catch (_: Exception) {
                    AlertDialog.Builder(host).setMessage("Email: support@kisamore.farm")
                        .setPositiveButton("Понятно", null).show()
                }
            }.show()
    }

    private fun settingsDialog() {
        val options = mutableListOf("Уведомления", "Тёмная тема", "Язык", "Помощь")
        if (user != null) options.add("Выйти")
        AlertDialog.Builder(host).setTitle("Настройки")
            .setItems(options.toTypedArray()) { _, i ->
                if (i == 4 && user != null) {
                    AlertDialog.Builder(host).setTitle("Выйти из аккаунта?")
                        .setNegativeButton("Отмена", null)
                        .setPositiveButton("Выйти") { _, _ -> onLogout() }.show()
                } else settingAction(i)
            }.setNegativeButton("Закрыть", null).show()
    }

    private fun confirmLogout() {
        AlertDialog.Builder(host).setTitle("Выйти из профиля?")
            .setNegativeButton("Отмена", null)
            .setPositiveButton("Выйти") { _, _ -> onLogout() }.show()
    }

    private fun changePhoto() {
        if (user == null) onLogin() else onChangePhoto()
    }

    private fun loadRemoteAvatar(image: ImageView, value: String) {
        val api = ApiClient(host.applicationContext)
        Thread {
            val bitmap = runCatching { api.loadBitmap(value) }.getOrNull()
            if (bitmap != null) {
                PhotoFrameCache.remember(value, bitmap)
                host.runOnUiThread {
                    if (!host.isFinishing && !host.isDestroyed && image.isAttachedToWindow) { image.setImageBitmap(bitmap); image.visibility = View.VISIBLE }
                }
            }
        }.start()
    }

    private fun loadAvatar(image: ImageView, value: String): Boolean {
        return try {
            val uri = Uri.parse(value)
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            host.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it, null, bounds)
            }
            var factor = 1
            while (maxOf(bounds.outHeight, bounds.outWidth) / factor > 500) factor *= 2
            val bitmap = host.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = factor })
            }
            if (bitmap != null) {
                image.setImageBitmap(bitmap)
                PhotoFrameCache.remember(value, bitmap)
            }
            bitmap != null
        } catch (_: Exception) { false }
    }

    private fun loadPlantPhoto(image: ImageView, url: String) {
        val api = ApiClient(host.applicationContext)
        val resolved = api.absolute(url) ?: return
        PhotoFrameCache.showPrevious(image, resolved)
        Thread {
            val bitmap = runCatching { api.loadBitmap(resolved) }.getOrNull()
            if (bitmap != null) {
                PhotoFrameCache.remember(resolved, bitmap)
                host.runOnUiThread {
                    if (!host.isFinishing && !host.isDestroyed && image.isAttachedToWindow) {
                        image.setImageBitmap(bitmap)
                        image.visibility = View.VISIBLE
                    }
                }
            }
        }.start()
    }

    private fun text(
        value: String, size: Float, color: Int, bold: Boolean = false, single: Boolean = false
    ) = TextView(host).apply {
        text = value
        textSize = size
        setTextColor(color)
        includeFontPadding = false
        if (bold) setTypeface(typeface, Typeface.BOLD)
        if (single) {
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
        }
    }

    private fun card(pad: Int): LinearLayout = column().apply {
        setPadding(dp(pad), dp(pad), dp(pad), dp(pad))
        background = rounded(Color.parseColor(if (night) "#1B2A22" else "#FFFFFF"), 19)
        elevation = dp(1).toFloat()
    }

    private fun column() = LinearLayout(host).apply { orientation = VERTICAL }
    private fun row() = LinearLayout(host).apply { orientation = HORIZONTAL }

    private fun weighted(view: View, relative: Float) {
        addView(view, LayoutParams(-1, 0, relative))
    }
    private fun gap() {
        addView(View(host), LayoutParams(1, dp(gapSize)))
    }
    private fun rounded(color: Int, radius: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
    }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
