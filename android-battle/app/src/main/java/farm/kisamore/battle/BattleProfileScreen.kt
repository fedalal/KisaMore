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
    private val onChangePhoto: () -> Unit,
    private val onLogin: () -> Unit,
    private val onPlant: () -> Unit,
    private val onHistory: () -> Unit,
    private val onRegion: () -> Unit,
    private val onLogout: () -> Unit
) : LinearLayout(host) {
    private val ink = Color.parseColor("#1A1C1A")
    private val secondary = Color.parseColor("#6B7268")
    private val accent = Color.parseColor("#4A7C59")
    private val olive = Color.parseColor("#8B9A7D")
    private val pale = Color.parseColor("#E8F0E8")
    private val bg = Color.parseColor("#F8F9F6")
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
            if (loadAvatar(portrait, avatarUri)) {
                avatarHolder.addView(portrait, FrameLayout.LayoutParams(dp(avatarSize), dp(avatarSize)))
            }
        }

        avatarHolder.addView(icon("camera", 15, Color.WHITE).apply {
            gravity = Gravity.CENTER
            background = rounded(accent, 20)
            setOnClickListener { changePhoto() }
            contentDescription = "Загрузить фотографию"
        }, FrameLayout.LayoutParams(dp(23), dp(23), Gravity.END or Gravity.BOTTOM))
        card.addView(avatarHolder, LayoutParams(dp(avatarSize), dp(avatarSize)))

        val details = column().apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(14), 0, 0, 0)
        }
        details.addView(text(user?.displayName ?: "Гость", if (shortScreen) 20f else 23f, ink, true, true))
        details.addView(text(user?.email ?: "Войдите в аккаунт", 12f, secondary, single = true))
        details.addView(text(if (user == null) "Войти" else "Изменить фото", 13f, accent).apply {
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
        return card
    }

    private fun statsRow(): View {
        val row = row()
        // The current battle API does not expose winner identity; do not guess victories.
        val victories = 0
        val values = listOf(
            Triple("battle", "Битв", battles.size.toString()),
            Triple("trophy", "Побед", victories.toString()),
            Triple("chart", "Рейтинг", "0")
        )
        values.forEachIndexed { i, item ->
            val box = card(if (shortScreen) 7 else 10).apply {
                orientation = HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            box.addView(icon(item.first, if (shortScreen) 19 else 23, olive).apply {
                background = rounded(bg, 10)
            }, LayoutParams(dp(if (shortScreen) 25 else 30), dp(if (shortScreen) 30 else 36)))
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
            setImageResource(android.R.drawable.ic_menu_gallery)
        }
        card.addView(thumb, LayoutParams(dp(dimension), dp(dimension)))
        battle?.rackPhotoUrl?.let { loadPlantPhoto(thumb, it) }

        val info = column().apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(11), 0, dp(5), 0)
        }
        info.addView(text("Мои растения", if (shortScreen) 16f else 18f, ink, true, true))
        info.addView(text(battle?.plantName ?: "Пока нет растения", 13f, secondary, single = true))
        info.addView(text(
            if (battle == null) "Выбрать битву" else
                if (battle.status == "growing") "Растёт" else "Участие в битве",
            11f, accent, single = true
        ))
        card.addView(info, LayoutParams(0, -2, 1f))
        card.addView(icon("chevron", 18, secondary), LayoutParams(dp(18), dp(18)))
        return card
    }

    private fun rewardsCard(): View {
        val card = card(if (shortScreen) 9 else 12)
        card.addView(heading("Награды", "Все награды  ›") { showRewards() },
            LayoutParams(-1, dp(27)))
        val earned = profile.badges
        card.addView(text(
            if (earned.isEmpty()) "Наград пока нет" else earned.take(2).joinToString(" · "),
            14f, if (earned.isEmpty()) secondary else accent, single = true
        ).apply {
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(5), 0, 0, 0)
        }, LayoutParams(-1, dp(26)))
        return card
    }

    private fun historyCard(): View {
        val card = card(if (shortScreen) 7 else 10)
        card.addView(heading("История битв", "Все битвы  ›") { onHistory() },
            LayoutParams(-1, dp(26)))
        val finished = battles.filter { it.status == "finished" }
        if (finished.isEmpty()) {
            card.addView(text("Пока нет завершённых битв", 13f, secondary).apply {
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
        card.addView(heading("Настройки", "") { settingsDialog() },
            LayoutParams(-1, dp(22)))
        val options = listOf(
            Triple("bell", "Уведомления", "›"),
            Triple("moon", "Тёмная тема", "›"),
            Triple("globe", "Язык", "Русский ›"),
            Triple("help", "Помощь", "›")
        )
        options.forEachIndexed { i, item ->
            val line = row().apply {
                gravity = Gravity.CENTER_VERTICAL
                minimumHeight = dp(if (shortScreen) 26 else 37)
                if (i < 3) {
                    background = rounded(if (i % 2 == 0) Color.WHITE else bg, 8)
                }
                setOnClickListener { settingAction(i) }
            }
            line.addView(icon(item.first, 22, secondary), LayoutParams(dp(31), dp(23)))
            line.addView(text(item.second, if (shortScreen) 14f else 15f, ink), LayoutParams(0, -2, 1f))
            line.addView(text(item.third, if (shortScreen) 13f else 14f, secondary))
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
        val trophies = profile.badges
        val actual = if (trophies.isEmpty()) "Наград пока нет." else
            trophies.joinToString("\n• ", "• ")
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
            1 -> AlertDialog.Builder(host).setMessage("Тёмная тема пока не реализована.")
                .setPositiveButton("Понятно", null).show()
            2 -> AlertDialog.Builder(host).setMessage("Сейчас доступен русский язык.")
                .setPositiveButton("Понятно", null).show()
            3 -> showHelp()
        }
    }

    private fun showHelp() {
        AlertDialog.Builder(host)
            .setTitle("Помощь")
            .setMessage("Нужна помощь с KisaMore Battle? Напишите в службу поддержки.")
            .setNegativeButton("Закрыть", null)
            .setPositiveButton("Написать") { _, _ ->
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

    private fun changePhoto() {
        if (user == null) onLogin() else onChangePhoto()
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
            if (bitmap != null) image.setImageBitmap(bitmap)
            bitmap != null
        } catch (_: Exception) { false }
    }

    private fun loadPlantPhoto(image: ImageView, url: String) {
        val api = ApiClient(host.applicationContext)
        val resolved = api.absolute(url) ?: return
        Thread {
            val bitmap = runCatching { api.loadBitmap(resolved) }.getOrNull()
            if (bitmap != null) host.runOnUiThread {
                if (!host.isFinishing && !host.isDestroyed && image.isAttachedToWindow) image.setImageBitmap(bitmap)
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
        background = rounded(Color.WHITE, 19)
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
