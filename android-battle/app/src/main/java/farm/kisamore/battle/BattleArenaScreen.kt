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
    private val cameras = battle.cameraViews.ifEmpty {
        listOf(BattleCamera("default", true, battle.rackPhotoUrl, null))
    }
    private val camera = cameras.firstOrNull { it.cameraId == cameraPreference }
        ?: cameras.firstOrNull { it.isPrimary } ?: cameras.first()
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
        val capture = instant(camera.capturedAt) ?: return "Фото: время неизвестно"
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
        val battleRow = HorizontalScrollView(host).apply { isHorizontalScrollBarEnabled = false }
        val buttons = row()
        val switched = (choices + battle).distinctBy { it.id }
            .filter { it.status != "finished" || it.id == battle.id }
        switched.forEachIndexed { i, candidate ->
            val title = candidate.title.ifBlank { "Битва " + (i + 1) }
            buttons.addView(chip(title, candidate.id == battle.id) { onBattle(candidate) },
                LinearLayout.LayoutParams(dp(if (title.length > 16) 130 else 110), dp(34)).apply {
                    rightMargin = dp(6)
                })
        }
        battleRow.addView(buttons)
        body.addView(battleRow, LinearLayout.LayoutParams(-1, dp(36)))

        body.addView(label(dayLabel() + "   ·   " + photoAge(), 11f, false, secondary),
            LinearLayout.LayoutParams(-1, dp(20)))

        val cameraRow = row()
        cameraRow.addView(label("КАМЕРА", 10f, true, secondary),
            LinearLayout.LayoutParams(dp(65), dp(32)))
        val cameraScroll = HorizontalScrollView(host).apply { isHorizontalScrollBarEnabled = false }
        val camChips = row()
        cameras.forEachIndexed { i, cam ->
            camChips.addView(chip(cameraName(cam, i), cam.cameraId == camera.cameraId, 79) {
                onCamera(cam.cameraId)
            }, LinearLayout.LayoutParams(-2, dp(30)).apply { rightMargin = dp(6) })
        }
        cameraScroll.addView(camChips)
        cameraRow.addView(cameraScroll, LinearLayout.LayoutParams(0, dp(32), 1f))
        body.addView(cameraRow)

        val videoRow = row()
        videoRow.addView(label("ВИДЕО", 10f, true, secondary),
            LinearLayout.LayoutParams(dp(65), dp(32)))
        val videoChoices = listOf("24 ч", "3 дня", "Полный")
        val videoEntry = mine ?: battle.entries.firstOrNull()
        videoChoices.forEachIndexed { index, title ->
            val candidateUrl = when (index) {
                0 -> videoEntry?.timelapse24hUrl
                1 -> videoEntry?.timelapse3dUrl
                else -> videoEntry?.timelapseFullUrl
            }
            val c = chip(title, index == 0, if (index == 2) 76 else 66) {
                if (!camera.isPrimary && cameras.size > 1) {
                    Toast.makeText(host, "Таймлапс этой камеры пока недоступен", Toast.LENGTH_SHORT).show()
                } else {
                    onVideo(candidateUrl)
                }
            }
            videoRow.addView(c, LinearLayout.LayoutParams(0, dp(30), 1f).apply {
                if (index != 2) rightMargin = dp(6)
            })
        }
        body.addView(videoRow)
        body.addView(photoPanel(), LinearLayout.LayoutParams(-1, dp(150)).apply { topMargin=dp(5) })

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
            body.addView(chartCard, LinearLayout.LayoutParams(-1, dp(128)).apply { topMargin=dp(3) })
            // graph selection works without rebuilding the remote photo.
            chartTarget = chartCard.getChildAt(0) as BattleActivityChart
        } else {
            body.addView(spectatorBlock(), spacedTop(12))
        }
    }

    private fun photoPanel(): View {
        val frame = FrameLayout(host).apply {
            background = round(color("#1E3025"), 13)
            clipToOutline = true
        }
        val image = ImageView(host).apply {
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "Фото выбранной камеры"
        }
        frame.addView(image, FrameLayout.LayoutParams(-1, -1))
        val photoUrl = api.absolute(camera.photoUrl ?: battle.rackPhotoUrl)
        if (photoUrl != null) {
            PhotoFrameCache.current(photoUrl)?.let { image.setImageBitmap(it) }
            Thread {
                val newBitmap = api.loadBitmap(photoUrl)
                if (newBitmap != null) {
                    PhotoFrameCache.remember(photoUrl, newBitmap)
                    host.runOnUiThread {
                        if (!host.isFinishing && !host.isDestroyed && image.isAttachedToWindow)
                            image.setImageBitmap(newBitmap)
                    }
                }
            }.start()
        }
        // Only on the primary overhead view: the translucent marker intentionally
        // covers a broad region, not a precise image-dependent rectangular border.
        if (mine != null && camera.isPrimary && mine.slotNumber in 1..6) {
            val slot = mine.slotNumber - 1
            val overlay = object : View(host) {
                private val marker = GradientDrawable(GradientDrawable.Orientation.TL_BR,
                    intArrayOf(Color.argb(110, 130, 200, 105), Color.argb(35, 130, 200, 105))).apply {
                    cornerRadius = dp(12).toFloat()
                }
                override fun onDraw(canvas: android.graphics.Canvas) {
                    val marginX = width*.065f
                    val contentW = width - marginX*2f
                    val rowH = (height-dp(28)) / 3f
                    val col = slot % 2; val r = slot / 2
                    marker.setBounds(
                        (marginX + col*contentW/2 + dp(4)).toInt(),
                        (dp(28) + r*rowH + dp(3)).toInt(),
                        (marginX + (col+1)*contentW/2 - dp(4)).toInt(),
                        (dp(28)+(r+1)*rowH-dp(3)).toInt()
                    )
                    marker.draw(canvas)
                }
            }
            frame.addView(overlay, FrameLayout.LayoutParams(-1, -1))
        }
        val header = row().apply {
            setPadding(dp(8), 0, dp(8), 0)
            setBackgroundColor(color("#31543D"))
        }
        header.addView(label("● LIVE   ПОЛКА " + battle.rackId, 10f, true, Color.WHITE),
            LinearLayout.LayoutParams(0, -1, 1f))
        if (mine != null) header.addView(label("МОЙ №" + mine.slotNumber, 10f, true,
            Color.parseColor("#E3F4D5")).apply {
            gravity = Gravity.CENTER
            setPadding(dp(10), 0, dp(10), 0)
            background = round(color("#51845D"), 9)
        }, LinearLayout.LayoutParams(-2, dp(21)))
        frame.addView(header, FrameLayout.LayoutParams(-1, dp(24), Gravity.TOP))
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
            val nameButton = when (kind) { "water" -> "Полить"; "nutrient" -> "Добавить"; else -> "Закрыть" }
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
            parent.addView(label("Команд пока нет",12f,false,secondary),
                LinearLayout.LayoutParams(-1,-1))
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
