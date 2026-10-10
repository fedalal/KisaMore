package farm.kisamore.battle

import android.app.Activity
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlin.math.max

/**
 * Compact, native Battle UI built from the approved 390x844 Figma screen.
 * It uses real battle cameras and actions, and never supplies fake demo events.
 * On smaller screens ScrollView remains an accessibility fallback rather than
 * cutting off a command or a chart.
 */
internal class BattleArenaScreen(
    private val host: Activity,
    private val api: ApiClient,
    private val battle: Battle,
    private val choices: List<Battle>,
    cameraPreference: String?,
    initialPeriod: Int,
    private val onBattle: (Battle) -> Unit,
    private val onCamera: (String) -> Unit,
    private val onPeriod: (Int) -> Unit,
    private val onCommand: (BattleEntry, String) -> Unit,
    private val onVideo: (String?) -> Unit,
    private val onJournal: (List<BattleAction>) -> Unit,
    private val onPredict: (BattleEntry) -> Unit,
    private val onJoin: () -> Unit
) : ScrollView(host) {
    private val d = resources.displayMetrics.density
    private fun dp(value: Int): Int = (value * d + .5f).toInt()
    private val dark = host.getSharedPreferences("battle_settings", 0).getBoolean("dark_mode", false)
    private val back = color(if (dark) "#101A14" else "#F8F9F6")
    private val cardBg = color(if (dark) "#1B2A22" else "#FFFFFF")
    private val ink = color(if (dark) "#F0F5F0" else "#26392E")
    private val secondary = color(if (dark) "#AEBBAF" else "#728075")
    private val green = color(if (dark) "#8CC89E" else "#4A7C59")
    private val buttonBg = color(if (dark) "#365E42" else "#4A7C59")
    private val line = color(if (dark) "#354B3B" else "#E4EBE3")
    private val tint = color(if (dark) "#294333" else "#ECF3E9")
    private val zone = ZoneId.systemDefault()
    // Only show cameras actually published by the server. Legacy rack photo is a
    // fallback image, never an invented extra camera button.
    private val cameras = battle.cameraViews
    private val camera = cameras.firstOrNull { it.cameraId == cameraPreference }
        ?: cameras.firstOrNull { it.isPrimary } ?: cameras.firstOrNull()
    private val mine = battle.mine
    private var chartPeriod = initialPeriod.coerceIn(1, 7)
    private var chartTarget: BattleActivityChart? = null

    private fun color(hex: String) = Color.parseColor(hex)
    private fun round(fill: Int, radius: Int, stroke: Int? = null): GradientDrawable =
        GradientDrawable().apply {
            setColor(fill); cornerRadius = dp(radius).toFloat()
            if (stroke != null) setStroke(dp(1), stroke)
        }
    private fun label(s: String, size: Float = 12f, bold: Boolean = false, color: Int = ink) =
        TextView(host).apply {
            text = s; textSize = size; setTextColor(color); includeFontPadding = false
            if (bold) setTypeface(typeface, Typeface.BOLD)
            maxLines = 1; ellipsize = TextUtils.TruncateAt.END
            gravity = Gravity.CENTER_VERTICAL
        }
    private fun spacedTop(n: Int) = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(n) }
    private fun chip(s: String, selected: Boolean, width: Int = 0, click: () -> Unit): TextView =
        label(s, 11f, selected, if (selected) Color.WHITE else ink).apply {
            gravity = Gravity.CENTER
            setPadding(dp(9), 0, dp(9), 0)
            background = round(if (selected) buttonBg else cardBg, 11, if (selected) null else line)
            minHeight = dp(32)
            isClickable = true
            setOnClickListener { click() }
            if (width > 0) minWidth = dp(width)
        }
    private fun row(): LinearLayout = LinearLayout(host).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
    }
    private fun column(): LinearLayout = LinearLayout(host).apply { orientation = LinearLayout.VERTICAL }
    private fun labelHeader(s: String, margin: Int = 7): View = label(s, 11f, true).also {
        it.setPadding(0, dp(margin), 0, dp(4))
    }
    private fun instant(raw: String?): Instant? {
        if (raw.isNullOrBlank()) return null
        return runCatching { OffsetDateTime.parse(raw).toInstant() }.getOrNull()
            ?: runCatching { Instant.parse(raw) }.getOrNull()
            ?: runCatching { LocalDateTime.parse(raw).atZone(zone).toInstant() }.getOrNull()
    }
    private fun photoAge(): String {
        val capture = instant(camera?.capturedAt) ?: return "Фото: время неизвестно"
        val mins = ChronoUnit.MINUTES.between(capture, Instant.now()).coerceAtLeast(0)
        return when {
            mins == 0L -> "Фото: только что"
            mins < 60 -> "Фото: " + mins + " мин назад"
            mins < 1440 -> "Фото: " + (mins / 60) + " ч назад"
            else -> "Фото: " + (mins / 1440) + " дн назад"
        }
    }
    private fun dayLabel(): String {
        val planted = instant(battle.plantedAt)
        return if (planted != null) {
            "День " + (ChronoUnit.DAYS.between(planted, Instant.now()) + 1).coerceAtLeast(1)
        } else when (battle.status) {
            "open" -> "Набор участников"
            "planting" -> "Посадка"
            "finished" -> "Завершена"
            else -> "Битва идёт"
        }
    }
    private fun actionText(a: BattleAction): String = when (a.kind) {
        "water" -> "Полив " + a.amount + " мл"
        "nutrient" -> "Питание " + a.amount + " мл"
        "shade" -> "Закрыто на " + a.amount + " мин"
        else -> "Команда: " + a.kind
    }
    private fun actionIcon(kind: String) = when (kind) {
        "water" -> "💧"; "nutrient" -> "⚗"; "shade" -> "☾"; else -> "·"
    }
    private fun whenText(a: BattleAction): String {
        val date = instant(a.completedAt) ?: instant(a.requestedAt) ?: return "—"
        val local = date.atZone(zone)
        val today = LocalDate.now(zone)
        return when (local.toLocalDate()) {
            today -> local.format(DateTimeFormatter.ofPattern("HH:mm"))
            today.minusDays(1) -> "Вчера"
            else -> local.format(DateTimeFormatter.ofPattern("dd.MM"))
        }
    }
    private fun cameraName(value: BattleCamera, i: Int): String {
        val id = value.cameraId
        return if (value.isPrimary) "Основная"
        else if (id.length in 3..15 && !id.matches(Regex("(?i)(video|camera|cam)[_-]?\\d+"))) id.replace('_', ' ')
        else "Камера " + (i + 1)
    }

    init {
        isFillViewport = true
        setBackgroundColor(back)
        isVerticalScrollBarEnabled = false
        val body = column().apply { setPadding(dp(16), dp(4), dp(16), dp(8)) }
        addView(body, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))
        // One horizontally scrollable row of generously sized Battle selectors.
        val battleRow = HorizontalScrollView(host).apply {
            isHorizontalScrollBarEnabled = false
        }
        val buttons = row()
        val switched = (choices + battle).distinctBy { it.id }
            .filter { it.status != "finished" || it.id == battle.id }
        switched.forEachIndexed { i, candidate ->
            val title = candidate.title.ifBlank { "Битва " + (i + 1) }
            val active = candidate.id == battle.id
            val owned = api.hasSession() && candidate.mine != null
            val selector = row().apply {
                gravity = Gravity.CENTER_VERTICAL
                setPadding(dp(7), 0, dp(7), 0)
                background = round(if (active) buttonBg else cardBg, 11,
                    if (active) null else line)
                isClickable = true
                isFocusable = true
                contentDescription = title + if (owned) ", участвую" else ""
                setOnClickListener { onBattle(candidate) }
            }
            if (owned) selector.addView(BattleTabGlyph(host, "trophy",
                if (active) Color.WHITE else green),
                LinearLayout.LayoutParams(dp(17), dp(17)).apply { rightMargin = dp(5) })
            selector.addView(label(title, 11f, active,
                if (active) Color.WHITE else ink).apply {
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(0, dp(34), 1f))
            buttons.addView(selector, LinearLayout.LayoutParams(dp(166), dp(34)).apply {
                rightMargin = dp(8)
            })
        }
        battleRow.addView(buttons)
        body.addView(battleRow, LinearLayout.LayoutParams(-1, dp(36)))

        body.addView(label(dayLabel() + "   ·   " + photoAge(), 11f, false, secondary),
            LinearLayout.LayoutParams(-1, dp(20)))

        // The LIVE header is outside the photograph and cannot conceal a tray.
        val header = row().apply {
            setPadding(dp(9), 0, dp(8), 0)
            background = round(color("#31543D"), 9)
        }
        header.addView(label("● LIVE · ПОЛКА " + battle.rackId, 10f, true, Color.WHITE),
            LinearLayout.LayoutParams(0, -1, 1f))
        if (mine != null) header.addView(label("МОЙ №" + mine.slotNumber, 10f, true,
            color("#E3F4D5")).apply {
            gravity = Gravity.CENTER
            setPadding(dp(10), 0, dp(10), 0)
            background = round(color("#51845D"), 9)
        }, LinearLayout.LayoutParams(-2, dp(20)))
        body.addView(header, LinearLayout.LayoutParams(-1, dp(24)).apply {
            topMargin = dp(5)
        })

        // A 44dp camera rail, 6dp gap, flexible central image, 6dp gap,
        // and a 44dp timelapse rail. Buttons reflect actual server cameras.
        val photoRow = row()
        val camerasRail = column().apply {
            background = round(cardBg, 11, line)
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
        }
        val cameraScroller = ScrollView(host).apply {
            isVerticalScrollBarEnabled = false
            isFillViewport = false
        }
        val cameraButtons = column().apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            setPadding(dp(3), dp(5), dp(3), 0)
        }
        if (cameras.isEmpty()) {
            cameraButtons.addView(label("—", 15f, false, secondary).apply {
                gravity = Gravity.CENTER
                contentDescription = "Камеры не подключены"
            }, LinearLayout.LayoutParams(dp(38), dp(44)))
        }
        cameras.forEachIndexed { i, cam ->
            val selected = camera?.cameraId == cam.cameraId
            val cameraButton = column().apply {
                gravity = Gravity.CENTER
                background = round(if (selected) buttonBg else tint, 9)
                isClickable = true
                isFocusable = true
                contentDescription = "Камера " + (i + 1) +
                    (if (selected) ", выбрана" else "") + ", " + cameraName(cam, i)
                setOnClickListener { if (!selected) onCamera(cam.cameraId) }
            }
            cameraButton.addView(BattleTabGlyph(host, "camera",
                if (selected) Color.WHITE else green),
                LinearLayout.LayoutParams(dp(21), dp(21)))
            cameraButton.addView(label("К" + (i + 1), 10f, selected,
                if (selected) Color.WHITE else secondary).apply {
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(-1, dp(17)))
            cameraButtons.addView(cameraButton, LinearLayout.LayoutParams(dp(38), dp(47)).apply {
                bottomMargin = dp(6)
            })
        }
        cameraScroller.addView(cameraButtons)
        camerasRail.addView(cameraScroller, LinearLayout.LayoutParams(dp(44), -1))
        photoRow.addView(camerasRail, LinearLayout.LayoutParams(dp(44), -1).apply {
            rightMargin = dp(6)
        })

        photoRow.addView(photoPanel(), LinearLayout.LayoutParams(0, -1, 1f).apply {
            rightMargin = dp(6)
        })

        val videosRail = column().apply {
            background = round(cardBg, 11, line)
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(3), dp(5), dp(3), 0)
        }
        val videoEntry = mine ?: battle.entries.firstOrNull()
        listOf("24 ч", "3 дня", "Всё").forEachIndexed { i, title ->
            val path = when (i) {
                0 -> videoEntry?.timelapse24hUrl
                1 -> videoEntry?.timelapse3dUrl
                else -> videoEntry?.timelapseFullUrl
            }
            val selected = i == 0
            val videoButton = column().apply {
                gravity = Gravity.CENTER
                background = round(if (selected) buttonBg else tint, 9)
                isClickable = true
                isFocusable = true
                contentDescription = "Таймлапс " +
                    (if (i == 2) "за весь период" else title) + " выбранной камеры"
                setOnClickListener {
                    if (camera != null && !camera.isPrimary) {
                        Toast.makeText(host, "Таймлапс этой камеры пока недоступен",
                            Toast.LENGTH_SHORT).show()
                    } else {
                        onVideo(path)
                    }
                }
            }
            videoButton.addView(BattleTabGlyph(host, "play",
                if (selected) Color.WHITE else green),
                LinearLayout.LayoutParams(dp(21), dp(21)))
            videoButton.addView(label(title, 10f, selected,
                if (selected) Color.WHITE else ink).apply {
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(-1, dp(17)))
            videosRail.addView(videoButton, LinearLayout.LayoutParams(dp(38), dp(47)).apply {
                bottomMargin = dp(6)
            })
        }
        photoRow.addView(videosRail, LinearLayout.LayoutParams(dp(44), -1))
        body.addView(photoRow, LinearLayout.LayoutParams(-1, dp(174)).apply {
            topMargin = dp(6)
        })

        if (mine != null) {
            body.addView(labelHeader("МОИ РЕСУРСЫ", 6))
            body.addView(resources(mine), LinearLayout.LayoutParams(-1, dp(117)))
            val actionHeader = row()
            actionHeader.addView(label("ПОСЛЕДНИЕ ДЕЙСТВИЯ", 11f, true),
                LinearLayout.LayoutParams(0, dp(25), 1f))
            actionHeader.addView(label("Все ›", 11f, true, green).apply {
                gravity = Gravity.CENTER_VERTICAL
                setOnClickListener { onJournal(mine.actions) }
            }, LinearLayout.LayoutParams(-2, dp(25)))
            body.addView(actionHeader, spacedTop(5))
            body.addView(journal(mine.actions), LinearLayout.LayoutParams(-1, dp(90)))
            body.addView(chartHeader(), spacedTop(7))
            val chartCard = FrameLayout(host).apply {
                background = round(cardBg, 14)
                addView(BattleActivityChart(host, mine.actions, dark, chartPeriod),
                    FrameLayout.LayoutParams(-1, -1))
            }
            body.addView(chartCard, LinearLayout.LayoutParams(-1, dp(120)).apply { topMargin=dp(3) })
            // graph selection works without rebuilding the remote photo.
            chartTarget = chartCard.getChildAt(0) as BattleActivityChart
        } else {
            body.addView(spectatorBlock(), spacedTop(12))
        }
    }

    private fun photoPanel(): View {
        val frame = FrameLayout(host).apply {
            background = round(color("#1E3025"), 11)
            clipToOutline = true
        }
        val image = ImageView(host).apply {
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "Фото полки с выбранной камеры"
        }
        frame.addView(image, FrameLayout.LayoutParams(-1, -1))
        var highlight: View? = null
        val photoUrl = api.absolute(camera?.photoUrl ?: battle.rackPhotoUrl)
        if (photoUrl != null) {
            PhotoFrameCache.current(photoUrl)?.let { image.setImageBitmap(it) }
            Thread {
                val newBitmap = api.loadBitmap(photoUrl)
                if (newBitmap != null) {
                    PhotoFrameCache.remember(photoUrl, newBitmap)
                    host.runOnUiThread {
                        if (!host.isFinishing && !host.isDestroyed && image.isAttachedToWindow) {
                            image.setImageBitmap(newBitmap)
                            highlight?.invalidate()
                        }
                    }
                }
            }.start()
        }

        // Keep the soft highlight anchored to the *actual displayed photograph*
        // (FIT_CENTER content bounds), not its black letterbox area. The approximate
        // 2x3 position is deliberately soft; camera calibration is not assumed.
        if (mine != null && (camera == null || camera.isPrimary) &&
            mine.slotNumber in 1..6) {
            val slot = mine.slotNumber - 1
            val overlay = object : View(host) {
                private val marker = GradientDrawable(GradientDrawable.Orientation.TL_BR,
                    intArrayOf(Color.argb(95, 130, 200, 105),
                        Color.argb(30, 130, 200, 105))).apply {
                    cornerRadius = dp(9).toFloat()
                }
                override fun onDraw(canvas: android.graphics.Canvas) {
                    val drawable = image.drawable ?: return
                    val sourceW = drawable.intrinsicWidth.toFloat()
                    val sourceH = drawable.intrinsicHeight.toFloat()
                    if (sourceW <= 0f || sourceH <= 0f) return
                    val scale = minOf(width / sourceW, height / sourceH)
                    val actualW = sourceW * scale
                    val actualH = sourceH * scale
                    val left = (width - actualW) / 2f
                    val top = (height - actualH) / 2f
                    val col = slot % 2
                    val row = slot / 2
                    val cellW = actualW / 2f
                    val cellH = actualH / 3f
                    val padx = cellW * .09f
                    val pady = cellH * .10f
                    marker.setBounds(
                        (left + col * cellW + padx).toInt(),
                        (top + row * cellH + pady).toInt(),
                        (left + (col + 1) * cellW - padx).toInt(),
                        (top + (row + 1) * cellH - pady).toInt()
                    )
                    marker.draw(canvas)
                }
            }
            highlight = overlay
            frame.addView(overlay, FrameLayout.LayoutParams(-1, -1))
            image.addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
                overlay.invalidate()
            }
            // A new cached frame keeps the same viewer; refresh the highlight
            // after the bitmap is swapped, too.
            image.addOnAttachStateChangeListener(object : View.OnAttachStateChangeListener {
                override fun onViewAttachedToWindow(v: View) { overlay.invalidate() }
                override fun onViewDetachedFromWindow(v: View) {}
            })
        }
        return frame
    }

    private fun resources(entry: BattleEntry): View {
        val parent = column().apply {
            background = round(cardBg, 14)
            setPadding(dp(8), dp(2), dp(8), dp(2))
        }
        val resources = listOf(
            Triple("Вода", Pair(battle.waterBudgetMl,entry.waterUsedMl), "water"),
            Triple("Питание", Pair(battle.nutrientBudgetMl,entry.nutrientUsedMl), "nutrient"),
            Triple("Без света", Pair(battle.shadeBudgetMinutes,entry.shadeUsedMinutes), "shade")
        )
        resources.forEachIndexed { i, data ->
            val (name, amounts, kind) = data
            val (budget, used) = amounts
            val remain = (budget - used).coerceAtLeast(0)
            val unit = if (kind == "shade") "мин" else "мл"
            val content = row()
            content.addView(label(when(kind){"water"->"💧";"nutrient"->"⚗";else->"☾"},18f,false,green),
                LinearLayout.LayoutParams(dp(29), -1))
            val lbl = column()
            lbl.addView(label(name, 11f, true))
            lbl.addView(label("$remain/$budget $unit", 10f, false, secondary))
            content.addView(lbl, LinearLayout.LayoutParams(0, -2, 1f))
            val progressTrack = FrameLayout(host).apply { background = round(line, 3) }
            val p = View(host).apply { background = round(green, 3) }
            progressTrack.addView(p, FrameLayout.LayoutParams(
                dp(64*remain/max(1,budget)),dp(5),Gravity.START or Gravity.CENTER_VERTICAL))
            content.addView(progressTrack, LinearLayout.LayoutParams(dp(64),dp(5)).apply { rightMargin=dp(7) })
            val nameButton = when (kind) { "water" -> "Полить"; "nutrient" -> "Добавить"; else -> "Использовать" }
            val enabled = battle.status == "growing" && remain > 0
            content.addView(label(nameButton, 11f, true, Color.WHITE).apply {
                gravity=Gravity.CENTER
                background=round(if (enabled) buttonBg else color("#737D74"),9)
                isEnabled=enabled
                setOnClickListener { onCommand(entry,kind) }
            }, LinearLayout.LayoutParams(dp(96),dp(32)))
            parent.addView(content, LinearLayout.LayoutParams(-1,dp(37)))
            if (i<2) parent.addView(View(host).apply { setBackgroundColor(line) },
                LinearLayout.LayoutParams(-1,dp(1)))
        }
        return parent
    }

    private fun journal(actions: List<BattleAction>): View {
        val parent=column().apply {
            background=round(cardBg,14); setPadding(dp(11),dp(3),dp(11),dp(3))
        }
        val list=actions.sortedByDescending { it.completedAt ?: it.requestedAt ?: "" }.take(3)
        if(list.isEmpty()){
            parent.addView(label("Команд пока нет",12f,false,secondary).apply {
                gravity = Gravity.CENTER_VERTICAL
            }, LinearLayout.LayoutParams(-1, dp(32)))
        } else list.forEachIndexed { i,action ->
            val r=row()
            r.addView(label(actionIcon(action.kind),16f,false,green),
                LinearLayout.LayoutParams(dp(27),-1))
            r.addView(label(whenText(action),10f,false,secondary),
                LinearLayout.LayoutParams(dp(57),-1))
            val suffix=when(action.status){
                "pending"->" · ожидает"
                "cancelled"->" · отменено"
                else->""
            }
            r.addView(label(actionText(action)+suffix,11f,i==0),
                LinearLayout.LayoutParams(0,-1,1f))
            parent.addView(r,LinearLayout.LayoutParams(-1,dp(27)))
            if(i<list.lastIndex)parent.addView(View(host).apply{setBackgroundColor(line)},
                LinearLayout.LayoutParams(-1,dp(1)))
        }
        return parent
    }

    private fun chartHeader(): View {
        val r=row()
        r.addView(label("АКТИВНОСТЬ",11f,true),LinearLayout.LayoutParams(0,dp(28),1f))
        for (days in listOf(1,3,7)) {
            val selected=days==chartPeriod
            val button=chip(if(days==1)"24 ч" else "$days дня".replace("7 дня","7 дней"),
                selected,0) {
                chartPeriod=days
                onPeriod(days)
                chartTarget?.selectPeriod(days)
                // Refresh the active-chip appearance as well.
                for (i in 1 until r.childCount) {
                    val child=r.getChildAt(i) as? TextView ?: continue
                    val period=listOf(1,3,7)[i-1]
                    child.setTextColor(if(period==days) Color.WHITE else ink)
                    child.background=round(if(period==days)buttonBg else cardBg,9,if(period==days)null else line)
                }
            }
            r.addView(button,LinearLayout.LayoutParams(0,dp(27),1f).apply {
                if(days!=7)rightMargin=dp(5)
            })
        }
        return r
    }

    private fun spectatorBlock(): View {
        val wrap=column()
        val card=column().apply {
            setPadding(dp(15),dp(14),dp(15),dp(12))
            background=round(cardBg,14)
        }
        card.addView(label("Вы наблюдаете за битвой",16f,true))
        card.addView(label("Ресурсы участников скрыты. Управляет растением только его владелец.",12f,false,secondary).apply{
            maxLines=3;ellipsize=null
        },LinearLayout.LayoutParams(-1,dp(52)))
        if (battle.status=="open") card.addView(chip("Занять место",true){onJoin()},
            LinearLayout.LayoutParams(-1,dp(36)))
        wrap.addView(card)
        wrap.addView(labelHeader("УЧАСТНИКИ",10))
        val members=row().apply{
            setPadding(dp(8),dp(8),dp(8),dp(8));background=round(cardBg,14)
        }
        battle.entries.take(6).forEach { entry ->
            members.addView(chip("#"+entry.slotNumber,false){onPredict(entry)},
                LinearLayout.LayoutParams(0,dp(31),1f).apply { rightMargin=dp(4) })
        }
        wrap.addView(members)
        wrap.addView(label("Нажмите на номер контейнера, чтобы выбрать фаворита.",11f,false,secondary),
            spacedTop(8))
        return wrap
    }
}
