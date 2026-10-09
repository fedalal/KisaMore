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
 * One-screen Profile. Builds ALL children synchronously in init.
 *
 * There are intentionally no onSizeChanged/onMeasure callbacks that remove/re-add
 * children: they caused an empty profile on some physical Android devices.
 * The content is a fixed-size set of compact rows with flexible empty gaps.
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
    private val ink = Color.rgb(26, 28, 26)
    private val secondary = Color.rgb(107, 114, 104)
    private val accent = Color.rgb(74, 124, 89)
    private val pale = Color.rgb(231, 240, 230)
    private val condensed = resources.configuration.screenHeightDp < 690
    private val small = resources.configuration.screenHeightDp < 510

    init {
        orientation = VERTICAL
        setBackgroundColor(Color.rgb(248, 249, 246))
        setPadding(dp(16), dp(if (small) 6 else 12), dp(16), dp(if (small) 6 else 12))
        // Build visible content ONCE during construction, before attachment.
        populate()
    }

    private fun populate() {
        val title = txt("Профиль", if (small) 24f else 27f, ink, true).apply {
            gravity = Gravity.CENTER_VERTICAL
        }
        block(title, if (small) 32 else 42)
        flexibleGap()

        block(profileCard(), if (small) 70 else if (condensed) 81 else 98)
        flexibleGap()

        block(statCards(), if (small) 54 else if (condensed) 62 else 75)
        flexibleGap()

        block(plantCard(), if (small) 66 else if (condensed) 78 else 92)
        flexibleGap()

        block(summaryCard("Награды",
            profile.badges.take(2).joinToString(" · ").ifBlank { "Награды появятся после участия" }) {
            val body = if (profile.badges.isEmpty()) "Наград пока нет." else profile.badges.joinToString("\n• ", "• ")
            AlertDialog.Builder(host).setTitle("Награды").setMessage(body)
                .setPositiveButton("Закрыть", null).show()
        }, if (small) 48 else if (condensed) 55 else 70)
        flexibleGap()

        val recent = battles.firstOrNull { it.status == "finished" }
        block(summaryCard("История битв",
            recent?.let { it.plantName + " · Завершена" } ?: "Завершённых битв пока нет", onHistory),
            if (small) 48 else if (condensed) 55 else 70)
        flexibleGap()

        block(summaryCard("Настройки", if (small) "Нажмите для открытия" else "Уведомления · Язык · Сервер") {
            showSettings()
        }, if (small) 48 else if (condensed) 55 else 70)
    }

    private fun profileCard(): View {
        val card = card(if (small) 8 else 12).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val dimension = if (small) 49 else if (condensed) 58 else 72
        val avatarLayer = FrameLayout(host)
        val photo = ImageView(host).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = round(pale, dimension / 2)
            clipToOutline = true
            setImageResource(android.R.drawable.ic_menu_myplaces)
            contentDescription = "Загрузить фотографию"
            setOnClickListener { changeAvatar() }
        }
        if (!avatarUri.isNullOrBlank()) setUserPhoto(photo, avatarUri)
        avatarLayer.addView(photo, FrameLayout.LayoutParams(dp(dimension), dp(dimension)))
        avatarLayer.addView(txt("⌾", 17f, Color.WHITE, true).apply {
            gravity = Gravity.CENTER
            background = round(accent, 16)
            setOnClickListener { changeAvatar() }
        }, FrameLayout.LayoutParams(dp(23), dp(23), Gravity.BOTTOM or Gravity.END))
        card.addView(avatarLayer, LayoutParams(dp(dimension), dp(dimension)))

        val copy = LinearLayout(host).apply {
            orientation = VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(13), 0, 0, 0)
        }
        copy.addView(txt(user?.displayName ?: "Гость", if (small) 17f else 20f, ink, true, true))
        copy.addView(txt(user?.email ?: "Войдите в аккаунт", 11f, secondary, single = true))
        copy.addView(txt(if (user == null) "Войти" else "Изменить фото", 13f, accent).apply {
            setPadding(0, dp(5), 0, 0)
            setOnClickListener { changeAvatar() }
        })
        card.addView(copy, LayoutParams(0, -2, 1f))
        return card
    }

    private fun statCards(): View {
        val row = LinearLayout(host).apply { orientation = HORIZONTAL }
        val values = listOf(
            Triple("⚔", "Битв", battles.size.toString()),
            Triple("✦", "Уровень", profile.level.toString()),
            Triple("◷", "Завершено", battles.count { it.status == "finished" }.toString())
        )
        values.forEachIndexed { index, item ->
            val box = card(if (small) 6 else 9).apply {
                orientation = HORIZONTAL
                gravity = Gravity.CENTER_VERTICAL
            }
            box.addView(txt(item.first, if (small) 14f else 18f, accent).apply {
                gravity = Gravity.CENTER
            }, LayoutParams(dp(if (small) 19 else 26), -1))
            val copy = LinearLayout(host).apply { orientation = VERTICAL }
            copy.addView(txt(item.second, if (small) 9f else 11f, secondary, single = true))
            copy.addView(txt(item.third, if (small) 17f else 22f, ink, true))
            box.addView(copy, LayoutParams(0, -2, 1f))
            row.addView(box, LayoutParams(0, -1, 1f).apply {
                if (index < 2) rightMargin = dp(6)
            })
        }
        return row
    }

    private fun plantCard(): View {
        val card = card(if (small) 8 else 12).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            isClickable = true
            setOnClickListener { onPlant() }
        }
        val battle = battles.firstOrNull { it.mine != null && it.status != "finished" }
        val dimension = if (small) 49 else if (condensed) 54 else 64
        val image = ImageView(host).apply {
            background = round(pale, 12)
            clipToOutline = true
            scaleType = ImageView.ScaleType.CENTER_CROP
            setImageResource(android.R.drawable.ic_menu_gallery)
        }
        card.addView(image, LayoutParams(dp(dimension), dp(dimension)))
        battle?.rackPhotoUrl?.let { loadPlantPhoto(image, it) }

        val labels = LinearLayout(host).apply {
            orientation = VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(10), 0, dp(5), 0)
        }
        labels.addView(txt("Моё растение", if (small) 13f else 16f, ink, true, true))
        labels.addView(txt(battle?.plantName ?: "Пока нет растения", if (small) 11f else 13f, secondary, single = true))
        if (!small && battle != null)
            labels.addView(txt(if (battle.status == "growing") "Растёт" else "Участие в битве", 11f, accent))
        card.addView(labels, LayoutParams(0, -2, 1f))
        card.addView(txt("›", 24f, secondary))
        return card
    }

    private fun summaryCard(name: String, summary: String, action: () -> Unit): View {
        val card = card(if (small) 7 else 10).apply {
            gravity = Gravity.CENTER_VERTICAL
            isClickable = true
            setOnClickListener { action() }
        }
        val heading = LinearLayout(host).apply {
            orientation = HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        heading.addView(txt(name, if (small) 13f else 16f, ink, true), LayoutParams(0, -2, 1f))
        heading.addView(txt("›", 18f, secondary))
        card.addView(heading)
        if (!small) card.addView(txt(summary, 11f, secondary, single = true))
        return card
    }

    private fun showSettings() {
        val names = mutableListOf("Уведомления", "Тёмная тема (скоро)", "Язык: Русский", "Переключить сервер")
        if (user != null) names.add("Выйти")
        AlertDialog.Builder(host).setTitle("Настройки").setItems(names.toTypedArray()) { _, index ->
            when (index) {
                0 -> try {
                    host.startActivity(Intent("android.settings.APP_NOTIFICATION_SETTINGS").apply {
                        putExtra("android.provider.extra.APP_PACKAGE", host.packageName)
                    })
                } catch (_: Exception) { }
                1 -> AlertDialog.Builder(host).setMessage("Тёмная тема пока недоступна.")
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

    private fun changeAvatar() {
        if (user == null) onLogin() else onChangePhoto()
    }

    private fun setUserPhoto(image: ImageView, value: String) {
        try {
            val uri = Uri.parse(value)
            val bitmap = host.contentResolver.openInputStream(uri)?.use {
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeStream(it, null, bounds)
                val maxSide = maxOf(bounds.outHeight, bounds.outWidth)
                var sample = 1
                while (maxSide / sample > 400) sample *= 2
                host.contentResolver.openInputStream(uri)?.use { stream ->
                    BitmapFactory.decodeStream(stream, null, BitmapFactory.Options().apply { inSampleSize = sample })
                }
            }
            if (bitmap != null) image.setImageBitmap(bitmap)
        } catch (_: Exception) {
            // The local image was moved or permissions changed; leave default avatar.
        }
    }

    private fun loadPlantPhoto(target: ImageView, url: String) {
        val api = ApiClient(host.applicationContext)
        val resolved = api.absolute(url) ?: return
        Thread {
            val bitmap = runCatching { api.loadBitmap(resolved) }.getOrNull()
            if (bitmap != null) host.runOnUiThread {
                if (!host.isFinishing && !host.isDestroyed && target.isAttachedToWindow)
                    target.setImageBitmap(bitmap)
            }
        }.start()
    }

    private fun block(view: View, heightDp: Int) {
        addView(view, LayoutParams(-1, dp(heightDp)))
    }

    private fun flexibleGap() {
        addView(View(host), LayoutParams(1, 0, 1f))
    }

    private fun card(pad: Int) = LinearLayout(host).apply {
        orientation = VERTICAL
        setPadding(dp(pad), dp(pad), dp(pad), dp(pad))
        background = round(Color.WHITE, 18)
    }

    private fun txt(
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

    private fun round(color: Int, radius: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(radius).toFloat()
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
