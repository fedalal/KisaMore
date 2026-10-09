package farm.kisamore.battle

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.graphics.Color
import android.graphics.BitmapFactory
import android.graphics.drawable.GradientDrawable
import android.graphics.Typeface
import android.view.Gravity
import android.view.View
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.app.AlertDialog

class BattleProfileScreen(
    private val host: Activity,
    private val user: UserInfo?,
    private val profile: GameProfile,
    private val battles: List<Battle>,
    avatarUri: String?,
    private val onChangePhoto: () -> Unit,
    private val onLogin: () -> Unit,
    private val onPlant: () -> Unit,
    private val onHistory: () -> Unit,
    private val onRegion: () -> Unit,
    private val onLogout: () -> Unit
) : ScrollView(host) {
    private val bg = Color.parseColor("#F8F9F6")
    private val ink = Color.parseColor("#1A1C1A")
    private val secondary = Color.parseColor("#6B7268")
    private val accent = Color.parseColor("#4A7C59")
    private val soft = Color.parseColor("#E9F1E8")
    private val body = LinearLayout(host).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(20), dp(26), dp(20), dp(30))
    }
    init {
        setBackgroundColor(bg)
        addView(body, LayoutParams(-1, -2))
        body.addView(txt("Профиль", 30f, ink, true))
        space(18)
        val top = card()
        val line = row()
        val photo = ImageView(host).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = rounded(soft, 44)
            clipToOutline = true
            setImageResource(android.R.drawable.ic_menu_myplaces)
            contentDescription = "Изменить фото"
            setOnClickListener { if (user == null) onLogin() else onChangePhoto() }
        }
        if (avatarUri != null) {
            try {
                host.contentResolver.openInputStream(Uri.parse(avatarUri))?.use {
                    BitmapFactory.decodeStream(it)?.let { bitmap -> photo.setImageBitmap(bitmap) }
                }
            } catch (_: Exception) {}
        }
        line.addView(photo, LinearLayout.LayoutParams(dp(86), dp(86)))
        val info = LinearLayout(host).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), 0, 0, 0)
        }
        info.addView(txt(user?.displayName ?: "Гость", 22f, ink, true))
        info.addView(txt(user?.email ?: "Войдите в аккаунт", 12f, secondary))
        info.addView(txt(if (user == null) "Войти" else "◉  Изменить фото", 14f, accent).apply {
            setPadding(0, dp(10), 0, dp(8))
            setOnClickListener { if (user == null) onLogin() else onChangePhoto() }
        })
        profile.badges.firstOrNull()?.let { info.addView(pill("✦  " + it)) }
        line.addView(info, LinearLayout.LayoutParams(0, -2, 1f))
        top.addView(line)
        body.addView(top)
        space(14)
        val stats = row()
        listOf(
            Triple("⚔", "Битв", battles.size.toString()),
            Triple("★", "Уровень", profile.level.toString()),
            Triple("◷", "Завершено", battles.count { it.status == "finished" }.toString())
        ).forEachIndexed { index, item ->
            val tile = card(dp(12))
            tile.addView(txt(item.first, 20f, accent))
            tile.addView(txt(item.second, 12f, secondary))
            tile.addView(txt(item.third, 23f, ink, true))
            stats.addView(tile, LinearLayout.LayoutParams(0, -2, 1f).apply {
                if (index < 2) rightMargin = dp(7)
            })
        }
        body.addView(stats)
        space(18)
        val plant = card()
        plant.addView(heading("Моё растение", "›", onPlant))
        insideSpace(plant)
        val active = battles.firstOrNull { it.mine != null && it.status != "finished" }
        if (active == null) {
            plant.addView(txt("Пока нет активного растения", 15f, secondary))
            plant.addView(txt("Выберите битву, чтобы начать выращивание", 12f, secondary))
        } else {
            plant.addView(txt(active.plantName, 18f, ink, true))
            plant.addView(txt(active.title, 13f, secondary))
            plant.addView(pill(if (active.status == "growing") "🌱  Растёт" else "🌱  Участие"))
        }
        plant.setOnClickListener { onPlant() }
        body.addView(plant)
        space(18)
        val achievements = card()
        achievements.addView(heading("Награды", "", null))
        insideSpace(achievements)
        if (profile.badges.isEmpty()) {
            achievements.addView(txt("Пока нет наград. Первые появятся за участие.", 14f, secondary))
        } else {
            profile.badges.forEach {
                achievements.addView(txt("✦  " + it, 15f, accent).apply {
                    background = rounded(soft, 14)
                    setPadding(dp(12), dp(10), dp(12), dp(10))
                }, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(8) })
            }
        }
        achievements.addView(txt("Уровень " + profile.level + " · " + profile.xp + " XP", 12f, secondary))
        body.addView(achievements)
        space(18)
        val history = card()
        history.addView(heading("История битв", "Все битвы  ›", onHistory))
        insideSpace(history)
        val completed = battles.filter { it.status == "finished" }
        if (completed.isEmpty()) history.addView(txt("Завершённых битв пока нет", 14f, secondary))
        completed.take(2).forEach {
            val item = row().apply { gravity = Gravity.CENTER_VERTICAL }
            val names = LinearLayout(host).apply { orientation = LinearLayout.VERTICAL }
            names.addView(txt(it.plantName, 16f, ink, true))
            names.addView(txt(it.title + " · Завершена", 12f, secondary))
            item.addView(names, LinearLayout.LayoutParams(0, -2, 1f))
            item.addView(txt("›", 22f, secondary))
            history.addView(item, LinearLayout.LayoutParams(-1, dp(58)))
        }
        body.addView(history)
        space(18)
        val settings = card()
        settings.addView(heading("Настройки", "", null))
        setting(settings, "♧", "Уведомления", "›") {
            try {
                val intent = Intent("android.settings.APP_NOTIFICATION_SETTINGS")
                intent.putExtra("android.provider.extra.APP_PACKAGE", host.packageName)
                host.startActivity(intent)
            } catch (_: Exception) {}
        }
        setting(settings, "◐", "Тёмная тема", "Скоро", null)
        setting(settings, "◎", "Язык", "Русский", null)
        setting(settings, "⇄", "Сервер", "›", onRegion)
        if (user != null) setting(settings, "↪", "Выйти", "›") {
            AlertDialog.Builder(host).setTitle("Выйти из аккаунта?")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Выйти") { _, _ -> onLogout() }.show()
        }
        body.addView(settings)
    }
    private fun heading(label: String, right: String, click: (() -> Unit)?): View = row().apply {
        gravity = Gravity.CENTER_VERTICAL
        addView(txt(label, 20f, ink, true), LinearLayout.LayoutParams(0, -2, 1f))
        addView(txt(right, 13f, secondary).apply {
            if (click != null) setOnClickListener { click() }
        })
    }
    private fun setting(parent: LinearLayout, icon: String, label: String, value: String, action: (() -> Unit)?) {
        parent.addView(row().apply {
            gravity = Gravity.CENTER_VERTICAL
            minimumHeight = dp(54)
            addView(txt(icon, 21f, accent), LinearLayout.LayoutParams(dp(37), -2))
            addView(txt(label, 15f, ink), LinearLayout.LayoutParams(0, -2, 1f))
            addView(txt(value, 12f, secondary))
            if (action != null) setOnClickListener { action() }
        })
    }
    private fun card(p: Int = dp(17)) = LinearLayout(host).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(p, p, p, p)
        background = rounded(Color.WHITE, 20)
    }
    private fun row() = LinearLayout(host).apply { orientation = LinearLayout.HORIZONTAL }
    private fun txt(value: String, size: Float, color: Int, bold: Boolean = false) = TextView(host).apply {
        text = value
        textSize = size
        setTextColor(color)
        if (bold) setTypeface(typeface, Typeface.BOLD)
    }
    private fun pill(s: String) = txt(s, 13f, accent).apply {
        background = rounded(soft, 18)
        setPadding(dp(11), dp(6), dp(11), dp(6))
    }
    private fun rounded(color: Int, radius: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
    }
    private fun space(h: Int) { body.addView(View(host), LinearLayout.LayoutParams(1, dp(h))) }
    private fun insideSpace(parent: LinearLayout) { parent.addView(View(host), LinearLayout.LayoutParams(1, dp(12))) }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
