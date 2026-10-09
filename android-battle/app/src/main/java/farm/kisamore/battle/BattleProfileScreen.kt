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
import java.util.Locale

/**
 * Compact, single-screen Profile. This is deliberately NOT a ScrollView:
 * details are available by tapping their summary cards instead of stacking long sections.
 * Profile dimensions adapt to the actual available view height (excluding status/nav bars).
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
    private val bg = Color.parseColor("#F8F9F6")
    private val ink = Color.parseColor("#1A1C1A")
    private val muted = Color.parseColor("#6B7268")
    private val green = Color.parseColor("#4A7C59")
    private val pale = Color.parseColor("#E7F0E6")
    private var lastHeightDp = -1
    private var compact = false
    private var tiny = false

    init {
        orientation = VERTICAL
        setBackgroundColor(bg)
        setPadding(dp(16), dp(8), dp(16), dp(8))
        // Always populate the profile immediately. A view can be attached with the
        // same measured size or before the first size-change callback is delivered.
        tiny = true
        compact = true
        render()
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        if (h <= 0) return
        val heightDp = (h / resources.displayMetrics.density).toInt()
        if (heightDp == lastHeightDp) return
        lastHeightDp = heightDp
        compact = heightDp < 605
        tiny = heightDp < 465
        render()
    }

    private fun render() {
        removeAllViews()
        // Keep the entire view visible even on shorter displays or with larger
        // system bars. The bottom navigation is outside this view.
        val baseHeights = intArrayOf(
            if (tiny) 30 else if (compact) 33 else 38,
            if (tiny) 70 else if (compact) 80 else 95,
            if (tiny) 53 else if (compact) 61 else 72,
            if (tiny) 64 else if (compact) 72 else 88,
            if (tiny) 54 else if (compact) 62 else 77,
            if (tiny) 54 else if (compact) 62 else 78,
            if (tiny) 45 else if (compact) 51 else 62
        )
        val available = if (lastHeightDp > 0) lastHeightDp - 16 else 400
        val scale = (available.toFloat() / baseHeights.sum().toFloat())
            .coerceIn(0.72f, 1f)
        val heights = baseHeights.map { (it * scale).toInt() }
        val (titleHeight, heroHeight, statsHeight, plantHeight,
            awardsHeight, historyHeight, settingsHeight) = heights

        val title = label("Профиль", if (compact) 25f else 29f, ink, bold = true)
        title.gravity = Gravity.CENTER_VERTICAL
        fixed(title, titleHeight)
        gap()
        fixed(profileCard(heroHeight), heroHeight)
        gap()
        fixed(statCards(statsHeight), statsHeight)
        gap()
        fixed(plantCard(plantHeight), plantHeight)
        gap()
        fixed(awardsCard(awardsHeight), awardsHeight)
        gap()
        fixed(historyCard(historyHeight), historyHeight)
        gap()
        fixed(settingsCard(settingsHeight), settingsHeight)
    }

    private fun profileCard(height: Int): View {
        val box = surface(if (compact) 9 else 13)
        box.orientation = HORIZONTAL
        box.gravity = Gravity.CENTER_VERTICAL
        val avatarSize = if (tiny) 48 else if (compact) 57 else 67
        val avatarFrame = FrameLayout(host)
        val image = ImageView(host).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = shape(pale, avatarSize / 2)
            clipToOutline = true
            setImageResource(android.R.drawable.ic_menu_myplaces)
            contentDescription = "Изменить фотографию"
            setOnClickListener { photoAction() }
        }
        if (avatarUri != null) loadAvatar(image, avatarUri)
        avatarFrame.addView(image, FrameLayout.LayoutParams(dp(avatarSize), dp(avatarSize)))
        val camera = label("⌾", 17f, Color.WHITE, bold = true).apply {
            gravity = Gravity.CENTER
            background = shape(green, 20)
            contentDescription = "Загрузить фото"
            setOnClickListener { photoAction() }
        }
        avatarFrame.addView(camera, FrameLayout.LayoutParams(dp(24), dp(24), Gravity.BOTTOM or Gravity.RIGHT))
        box.addView(avatarFrame, LayoutParams(dp(avatarSize), dp(avatarSize)))

        val info = LinearLayout(host).apply {
            orientation = VERTICAL
            setPadding(dp(12), 0, 0, 0)
            gravity = Gravity.CENTER_VERTICAL
        }
        info.addView(label(user?.displayName ?: "Гость", if (compact) 18f else 20f, ink, bold = true, single = true))
        info.addView(label(user?.email ?: "Войдите в аккаунт", 11f, muted, single = true))
        val photoLink = label(if (user == null) "Войти" else "Изменить фото", if (tiny) 11f else 13f, green)
        photoLink.setPadding(0, dp(if (tiny) 3 else 6), 0, 0)
        photoLink.setOnClickListener { photoAction() }
        info.addView(photoLink)
        box.addView(info, LayoutParams(0, -2, 1f))
        return box
    }

    private fun statCards(height: Int): View {
        val group = LinearLayout(host).apply { orientation = HORIZONTAL }
        val completed = battles.count { it.status == "finished" }
        val values = listOf(
            Triple("⚔", "Битв", battles.size.toString()),
            Triple("✦", "Уровень", profile.level.toString()),
            Triple("◷", "Завершено", completed.toString())
        )
        values.forEachIndexed { index, item ->
            val tile = surface(if (compact) 8 else 10).apply {
                orientation = HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            val symbol = label(item.first, if (compact) 17f else 20f, green)
            symbol.gravity = Gravity.CENTER
            tile.addView(symbol, LayoutParams(dp(if (tiny) 21 else 28), -1))
            val textGroup = LinearLayout(host).apply { orientation = VERTICAL }
            textGroup.addView(label(item.second, if (tiny) 10f else 11f, muted, single = true))
            textGroup.addView(label(item.third, if (compact) 18f else 22f, ink, bold = true))
            tile.addView(textGroup, LayoutParams(0, -2, 1f))
            group.addView(tile, LayoutParams(0, -1, 1f).apply {
                if (index != values.lastIndex) rightMargin = dp(7)
            })
        }
        return group
    }

    private fun plantCard(height: Int): View {
        val box = surface(if (compact) 9 else 13).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setOnClickListener { onPlant() }
        }
        val battle = battles.firstOrNull { it.mine != null && it.status != "finished" }
        val size = height - (if (compact) 18 else 26)
        val thumbnail = ImageView(host).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP // never stretch plant photographs
            background = shape(pale, 12)
            clipToOutline = true
            setImageResource(android.R.drawable.ic_menu_gallery)
        }
        box.addView(thumbnail, LayoutParams(dp(size), dp(size)))
        battle?.rackPhotoUrl?.let { url -> fetchPlantPhoto(thumbnail, url) }
        val text = LinearLayout(host).apply {
            orientation = VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(11), 0, dp(3), 0)
        }
        text.addView(label("Моё растение", if (tiny) 13f else 15f, ink, bold = true, single = true))
        text.addView(label(battle?.plantName ?: "Пока нет растения", if (tiny) 12f else 14f, muted, single = true))
        if (!tiny && battle != null) {
            text.addView(label(if (battle.status == "growing") "Растёт" else "Участвует в битве", 11f, green, single = true))
        }
        box.addView(text, LayoutParams(0, -2, 1f))
        box.addView(label("›", 22f, muted))
        return box
    }

    private fun awardsCard(height: Int): View {
        val box = surface(if (compact) 8 else 12)
        box.gravity = Gravity.CENTER_VERTICAL
        val heading = horizontal()
        heading.addView(label("Награды", if (tiny) 14f else 16f, ink, bold = true), LayoutParams(0, -2, 1f))
        heading.addView(label("Все  ›", 11f, muted))
        box.addView(heading)
        val badges = profile.badges
        val summary = if (badges.isEmpty()) "Пока нет наград" else badges.take(2).joinToString("  ·  ")
        box.addView(label(summary, if (tiny) 11f else 12f, if (badges.isEmpty()) muted else green, single = true))
        box.setOnClickListener {
            AlertDialog.Builder(host)
                .setTitle("Награды")
                .setMessage(if (badges.isEmpty()) "Награды появятся после участия в битвах." else badges.joinToString("\n• ", "• "))
                .setPositiveButton("Закрыть", null).show()
        }
        return box
    }

    private fun historyCard(height: Int): View {
        val box = surface(if (compact) 8 else 12)
        box.gravity = Gravity.CENTER_VERTICAL
        val heading = horizontal()
        heading.addView(label("История битв", if (tiny) 14f else 16f, ink, bold = true), LayoutParams(0, -2, 1f))
        heading.addView(label("Все  ›", 11f, muted))
        box.addView(heading)
        val recent = battles.firstOrNull { it.status == "finished" }
        box.addView(label(
            if (recent == null) "Завершённых битв пока нет" else recent.plantName + " · Завершена",
            if (tiny) 11f else 12f, muted, single = true
        ))
        box.setOnClickListener { onHistory() }
        return box
    }

    private fun settingsCard(height: Int): View {
        val box = surface(if (compact) 8 else 12).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val info = LinearLayout(host).apply { orientation = VERTICAL }
        info.addView(label("Настройки", if (tiny) 14f else 16f, ink, bold = true))
        if (!tiny) info.addView(label("Уведомления · Язык · Сервер", 11f, muted, single = true))
        box.addView(info, LayoutParams(0, -2, 1f))
        box.addView(label("›", 23f, muted))
        box.setOnClickListener { settingsDialog() }
        return box
    }

    private fun settingsDialog() {
        val items = mutableListOf("Уведомления", "Тёмная тема (скоро)", "Язык: Русский", "Переключить сервер")
        if (user != null) items.add("Выйти из аккаунта")
        AlertDialog.Builder(host).setTitle("Настройки")
            .setItems(items.toTypedArray()) { _, index ->
                when (index) {
                    0 -> {
                        try {
                            val intent = Intent("android.settings.APP_NOTIFICATION_SETTINGS").apply {
                                putExtra("android.provider.extra.APP_PACKAGE", host.packageName)
                            }
                            host.startActivity(intent)
                        } catch (_: Exception) {}
                    }
                    1 -> AlertDialog.Builder(host).setMessage("Тёмная тема появится в следующем обновлении.")
                        .setPositiveButton("Понятно", null).show()
                    2 -> AlertDialog.Builder(host).setMessage("Сейчас доступен русский язык.")
                        .setPositiveButton("Понятно", null).show()
                    3 -> onRegion()
                    4 -> AlertDialog.Builder(host).setTitle("Выйти из аккаунта?")
                        .setNegativeButton("Отмена", null)
                        .setPositiveButton("Выйти") { _, _ -> onLogout() }.show()
                }
            }.setNegativeButton("Закрыть", null).show()
    }

    private fun photoAction() {
        if (user == null) onLogin() else onChangePhoto()
    }

    private fun loadAvatar(image: ImageView, value: String) {
        try {
            val uri = Uri.parse(value)
            val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            host.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) }
            val large = maxOf(options.outWidth, options.outHeight)
            var sample = 1
            while (large / sample > 512) sample *= 2
            val bitmap = host.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample })
            }
            if (bitmap != null) image.setImageBitmap(bitmap)
        } catch (_: Exception) {
            // A missing/deleted photo gracefully reverts to the default avatar.
        }
    }

    private fun fetchPlantPhoto(image: ImageView, url: String) {
        val absolute = ApiClient(host.applicationContext).absolute(url) ?: return
        Thread {
            val bitmap = runCatching { ApiClient(host.applicationContext).loadBitmap(absolute) }.getOrNull()
            if (bitmap != null) host.runOnUiThread {
                if (!host.isFinishing && !host.isDestroyed && image.isAttachedToWindow) image.setImageBitmap(bitmap)
            }
        }.start()
    }

    private fun surface(padding: Int): LinearLayout = LinearLayout(host).apply {
        orientation = VERTICAL
        setPadding(dp(padding), dp(padding), dp(padding), dp(padding))
        background = shape(Color.WHITE, if (compact) 17 else 20)
    }

    private fun horizontal() = LinearLayout(host).apply {
        orientation = HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
    }

    private fun label(
        value: String,
        size: Float,
        color: Int,
        bold: Boolean = false,
        single: Boolean = false
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

    private fun fixed(view: View, height: Int) {
        addView(view, LayoutParams(-1, dp(height)))
    }

    // Weighted gaps consume all remaining space; card heights never grow / stretch.
    private fun gap() {
        addView(View(host), LayoutParams(1, 0, 1f))
    }

    private fun shape(color: Int, radius: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
